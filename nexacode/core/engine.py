"""
+======================================================================+
|                   NEXACODE AI ENGINE v2.1                             |
|            Multi-Provider AI Communication Layer                      |
|     Fixed: ResponseNotRead, Gemini SSE, Anthropic Stream,            |
|            Error Recovery, Context Preservation, Rate Limits,         |
|            Gemini 2.5 Support, Retry Logic, THINKING MODE,           |
|            Deep-Think planning, Task-specific prompts                |
+======================================================================+
"""

import os
import json
import time
import httpx
import asyncio
from typing import AsyncGenerator, Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from nexacode.config.settings import ModelConfig, NexaCodeConfig


# =====================================================================
# DATA MODELS
# =====================================================================

@dataclass
class Message:
    """A single message in a conversation."""
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    tool_call_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    tokens_used: int = 0
    model: str = ""
    cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_api_dict(self, provider: str = "openai") -> dict:
        """Convert to provider-specific API format."""
        if provider == "anthropic":
            return self._to_anthropic()
        elif provider == "gemini":
            return self._to_gemini()
        else:
            return self._to_openai()

    def _to_openai(self) -> dict:
        d = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    def _to_anthropic(self) -> dict:
        if self.role == "system":
            return None  # Handled separately in payload
        return {"role": self.role, "content": self.content}

    def _to_gemini(self) -> dict:
        role_map = {"user": "user", "assistant": "model", "system": "user"}
        return {
            "role": role_map.get(self.role, "user"),
            "parts": [{"text": self.content}],
        }


@dataclass
class Conversation:
    """A full conversation with history and context preservation."""
    messages: List[Message] = field(default_factory=list)
    system_prompt: str = ""
    total_tokens: int = 0
    total_cost: float = 0.0
    model: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    _retry_buffer: Optional[Message] = field(default=None, repr=False)

    def add_message(self, role: str, content: str, **kwargs) -> Message:
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        return msg

    def get_context(self, max_messages: int = 50) -> List[Message]:
        """Get recent conversation context."""
        return self.messages[-max_messages:]

    def save_retry_point(self):
        """Save the last user message for retry capability."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                self._retry_buffer = msg
                break

    def pop_last_failed(self):
        """Remove the last incomplete assistant message (for retry)."""
        if self.messages and self.messages[-1].role == "assistant":
            self.messages.pop()

    def clear(self):
        self.messages.clear()
        self.total_tokens = 0
        self.total_cost = 0.0
        self._retry_buffer = None


# =====================================================================
# ERROR TYPES
# =====================================================================

class AIEngineError(Exception):
    """Base error for AI Engine."""
    pass


class ProviderConnectionError(AIEngineError):
    """Could not connect to the AI provider."""
    def __init__(self, provider: str, url: str, original: Exception = None):
        self.provider = provider
        self.url = url
        self.original = original
        super().__init__(f"Connection to {provider} at {url} failed")


class ProviderAuthError(AIEngineError):
    """Authentication failed."""
    def __init__(self, provider: str, status: int, detail: str = ""):
        self.provider = provider
        self.status = status
        self.detail = detail
        super().__init__(f"{provider} auth error ({status}): {detail}")


class ProviderRateLimit(AIEngineError):
    """Rate limited by provider (temporary, retryable)."""
    def __init__(self, provider: str, retry_after: float = 0):
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(f"{provider} rate limited. Retry after {retry_after}s")


class ProviderQuotaExhausted(AIEngineError):
    """Quota/daily limit exhausted (NOT retryable — must switch model)."""
    def __init__(self, provider: str, model_id: str, detail: str = ""):
        self.provider = provider
        self.model_id = model_id
        self.detail = detail
        super().__init__(f"{provider} quota exhausted for {model_id}: {detail}")


class ProviderAPIError(AIEngineError):
    """General API error from provider."""
    def __init__(self, provider: str, status: int, body: str = ""):
        self.provider = provider
        self.status = status
        self.body = body
        super().__init__(f"{provider} API error ({status})")


# =====================================================================
# AI ENGINE - CORE
# =====================================================================

class AIEngine:
    """
    Multi-provider AI engine with robust streaming, error recovery,
    and context preservation.
    
    Supported providers:
    - OpenAI (GPT-4o, GPT-4, GPT-3.5, o1, o3)
    - Anthropic (Claude 3.5 Sonnet, Claude 3 Opus, Haiku)
    - Google Gemini (2.0 Flash, 1.5 Pro)
    - OpenRouter (any model via unified API)
    - Groq (Llama 3, Mixtral, Gemma)
    - DeepSeek (Chat, Coder, Reasoner)
    - Together AI (Llama, Mixtral)
    - Ollama (local, any model)
    - LM Studio (local, any model)
    - Any Custom OpenAI-compatible endpoint
    """

    def __init__(self, config: NexaCodeConfig):
        self.config = config
        self.conversations: Dict[str, Conversation] = {}
        self.active_conversation: str = "default"
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self.token_usage: Dict[str, int] = {"input": 0, "output": 0}
        self.total_cost: float = 0.0
        self.request_count: int = 0
        self.error_count: int = 0
        self.last_error: Optional[str] = None

    # -----------------------------------------------------------------
    # CONVERSATION MANAGEMENT
    # -----------------------------------------------------------------
    def get_conversation(self, name: str = None) -> Conversation:
        name = name or self.active_conversation
        if name not in self.conversations:
            self.conversations[name] = Conversation()
        return self.conversations[name]

    def switch_conversation(self, name: str):
        self.active_conversation = name

    def list_conversations(self) -> List[str]:
        return list(self.conversations.keys())

    # -----------------------------------------------------------------
    # HTTP CLIENT MANAGEMENT
    # -----------------------------------------------------------------
    def _get_client(self, model_config: ModelConfig) -> httpx.AsyncClient:
        """Get or create an HTTP client for the given provider."""
        key = f"{model_config.provider}_{model_config.base_url}"
        if key not in self._clients:
            headers = {"Content-Type": "application/json"}
            headers.update(model_config.headers)

            if model_config.provider == "anthropic":
                headers["x-api-key"] = model_config.api_key
                headers["anthropic-version"] = "2023-06-01"
            elif model_config.provider == "gemini":
                pass  # API key goes in URL query param
            else:
                if model_config.api_key:
                    headers["Authorization"] = f"Bearer {model_config.api_key}"

            self._clients[key] = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(model_config.timeout, connect=30.0),
                follow_redirects=True,
            )
        return self._clients[key]

    # -----------------------------------------------------------------
    # URL BUILDING
    # -----------------------------------------------------------------
    def _build_url(self, model_config: ModelConfig, stream: bool = True) -> str:
        """Build the correct API URL for each provider."""
        if model_config.provider == "anthropic":
            base = model_config.base_url or "https://api.anthropic.com/v1"
            return f"{base}/messages"

        elif model_config.provider == "gemini":
            base = model_config.base_url or "https://generativelanguage.googleapis.com/v1beta"
            # Use streamGenerateContent for streaming, generateContent otherwise
            action = "streamGenerateContent" if stream else "generateContent"
            url = f"{base}/models/{model_config.model_id}:{action}?key={model_config.api_key}"
            if stream:
                url += "&alt=sse"
            return url

        else:  # OpenAI-compatible (openai, openrouter, groq, deepseek, together, ollama, lmstudio, custom)
            base = model_config.base_url or "https://api.openai.com/v1"
            return f"{base}/chat/completions"

    # -----------------------------------------------------------------
    # THINKING MODE SUPPORT (Gemini 2.5 models)
    # -----------------------------------------------------------------
    def _is_thinking_model(self, model_config: ModelConfig) -> bool:
        """Check if this model supports thinking/reasoning mode."""
        from nexacode.config.settings import DEFAULT_PROVIDERS
        if model_config.provider == "gemini":
            provider_info = DEFAULT_PROVIDERS.get("gemini", {})
            thinking_models = provider_info.get("thinking_models", [])
            return model_config.model_id in thinking_models
        # DeepSeek reasoner also supports thinking
        if model_config.provider == "deepseek" and "reasoner" in model_config.model_id:
            return True
        return False

    # -----------------------------------------------------------------
    # PAYLOAD BUILDING
    # -----------------------------------------------------------------
    def _build_payload(
        self,
        model_config: ModelConfig,
        messages: List[Message],
        system_prompt: str = "",
        stream: bool = True,
    ) -> dict:
        """Build provider-specific request payload."""
        provider = model_config.provider

        if provider == "anthropic":
            api_messages = []
            for m in messages:
                if m.role != "system":
                    d = m.to_api_dict("anthropic")
                    if d:
                        api_messages.append(d)
            payload = {
                "model": model_config.model_id,
                "max_tokens": model_config.max_tokens,
                "temperature": model_config.temperature,
                "stream": stream,
                "messages": api_messages,
            }
            if system_prompt:
                payload["system"] = system_prompt
            return payload

        elif provider == "gemini":
            contents = []
            for m in messages:
                if m.role != "system":
                    contents.append(m.to_api_dict("gemini"))
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": model_config.temperature,
                    "maxOutputTokens": model_config.max_tokens,
                    "topP": model_config.top_p,
                },
            }
            if system_prompt:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_prompt}]
                }
            # Enable thinking/reasoning for supported models
            if self._is_thinking_model(model_config):
                payload["generationConfig"]["thinkingConfig"] = {
                    "thinkingBudget": 8192
                }
            return payload

        else:  # OpenAI-compatible
            api_messages = []
            if system_prompt:
                api_messages.append({"role": "system", "content": system_prompt})
            for m in messages:
                if m.role != "system":
                    api_messages.append(m.to_api_dict("openai"))
            payload = {
                "model": model_config.model_id,
                "messages": api_messages,
                "max_tokens": model_config.max_tokens,
                "temperature": model_config.temperature,
                "top_p": model_config.top_p,
                "stream": stream,
            }
            # Only add penalties if they're non-zero (some providers don't support them)
            if model_config.frequency_penalty:
                payload["frequency_penalty"] = model_config.frequency_penalty
            if model_config.presence_penalty:
                payload["presence_penalty"] = model_config.presence_penalty
            return payload

    # -----------------------------------------------------------------
    # MAIN CHAT METHOD
    # -----------------------------------------------------------------
    async def chat(
        self,
        prompt: str,
        model_name: str = None,
        system_prompt: str = "",
        conversation: str = None,
        stream: bool = True,
        retry_count: int = 0,
        max_retries: int = 4,
    ) -> AsyncGenerator[str, None]:
        """
        Send a message and stream the response.
        
        Handles:
        - Automatic retry on transient errors
        - Context preservation on failure
        - Proper error messages with actionable hints
        """
        model_name = model_name or self.config.active_model
        model_config = self.config.models.get(model_name)
        if not model_config:
            yield f"\n\033[91m!! Model '{model_name}' not found.\033[0m\n"
            yield f"\033[93m   Fix: Run /model add  or  /apikey <provider> <key>\033[0m\n"
            yield f"\033[93m   Available: /model list  |  /providers\033[0m\n"
            return

        if not model_config.api_key and model_config.provider not in ("ollama", "lmstudio"):
            yield f"\n\033[91m!! No API key set for '{model_config.provider}'.\033[0m\n"
            yield f"\033[93m   Fix: /apikey {model_config.provider} YOUR_KEY\033[0m\n"
            return

        conv = self.get_conversation(conversation)
        conv.add_message("user", prompt)
        conv.save_retry_point()  # Save for retry capability

        url = self._build_url(model_config, stream=stream)
        client = self._get_client(model_config)
        payload = self._build_payload(
            model_config,
            conv.get_context(),
            system_prompt=system_prompt or conv.system_prompt,
            stream=stream,
        )

        full_response = ""
        self.request_count += 1

        try:
            if stream:
                async for chunk in self._stream_request(client, url, payload, model_config):
                    full_response += chunk
                    yield chunk
            else:
                result = await self._simple_request(client, url, payload, model_config)
                full_response = result
                yield result

            # Save assistant response
            conv.add_message("assistant", full_response, model=model_name)
            self._update_usage(model_config, prompt, full_response)
            self.last_error = None

        except httpx.ConnectError as e:
            self.error_count += 1
            self.last_error = str(e)
            conv.pop_last_failed()
            error_msg = self._format_connection_error(model_config)
            yield error_msg

        except httpx.TimeoutException:
            self.error_count += 1
            conv.pop_last_failed()
            yield (
                f"\n\033[91m!! Request timed out after {model_config.timeout}s\033[0m\n"
                f"\033[93m   Fix: /config set timeout 180  (increase timeout)\033[0m\n"
                f"\033[93m   Or try a faster model: /model list\033[0m\n"
            )

        except ProviderAuthError as e:
            self.error_count += 1
            conv.pop_last_failed()
            yield (
                f"\n\033[91m!! Authentication failed for {e.provider} (HTTP {e.status})\033[0m\n"
                f"\033[93m   Fix: /apikey {e.provider} YOUR_NEW_KEY\033[0m\n"
                f"\033[93m   Detail: {e.detail[:200]}\033[0m\n"
            )

        except ProviderQuotaExhausted as e:
            self.error_count += 1
            conv.pop_last_failed()
            # Try auto-fallback to another model from same provider
            fallback = self._find_fallback_model(model_name, e.model_id)
            if fallback:
                yield (
                    f"\n\033[93m!! Quota exhausted for '{e.model_id}'. "
                    f"Auto-switching to '{fallback}'...\033[0m\n"
                )
                # Remove the user message (it'll be re-added in the retry)
                if conv.messages and conv.messages[-1].role == "user":
                    conv.messages.pop()
                self.config.active_model = fallback
                self.config.save_config()
                async for chunk in self.chat(
                    prompt, fallback, system_prompt, conversation,
                    stream, 0, max_retries,
                ):
                    yield chunk
            else:
                yield (
                    f"\n\033[91m!! QUOTA EXHAUSTED for '{e.model_id}' on {e.provider}.\033[0m\n"
                    f"\033[91m   This model's daily/free-tier quota is used up.\033[0m\n"
                    f"\033[91m   Retrying will NOT help — you must switch models.\033[0m\n"
                    f"\033[93m   Fix: /model list  → pick another model\033[0m\n"
                    f"\033[93m   Tip: gemini-2.5-flash has the highest free-tier quota\033[0m\n"
                    f"\033[93m   Detail: {e.detail[:200]}\033[0m\n"
                )

        except ProviderRateLimit as e:
            self.error_count += 1
            conv.pop_last_failed()
            if retry_count < max_retries:
                wait = max(e.retry_after, 3.0) * (retry_count + 1)  # Exponential backoff
                yield f"\n\033[93m   Rate limited (temporary). Retrying in {wait:.0f}s... (attempt {retry_count + 1}/{max_retries})\033[0m\n"
                await asyncio.sleep(wait)
                # Retry - remove the user message we added (it'll be re-added)
                if conv.messages and conv.messages[-1].role == "user":
                    conv.messages.pop()
                async for chunk in self.chat(
                    prompt, model_name, system_prompt, conversation,
                    stream, retry_count + 1, max_retries,
                ):
                    yield chunk
            else:
                yield (
                    f"\n\033[91m!! Rate limited by {e.provider}. Max retries exceeded.\033[0m\n"
                    f"\033[93m   Fix: Wait a moment and try again\033[0m\n"
                    f"\033[93m   Or switch models: /model list\033[0m\n"
                )

        except ProviderAPIError as e:
            self.error_count += 1
            conv.pop_last_failed()
            yield (
                f"\n\033[91m!! {e.provider} API error (HTTP {e.status})\033[0m\n"
                f"\033[93m   {e.body[:300]}\033[0m\n"
                f"\033[93m   Fix: Check model name with /model list\033[0m\n"
            )

        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            conv.pop_last_failed()
            yield (
                f"\n\033[91m!! Unexpected error: {type(e).__name__}: {str(e)[:300]}\033[0m\n"
                f"\033[93m   Try: /clear to reset conversation, or /model list to switch models\033[0m\n"
            )

    # -----------------------------------------------------------------
    # STREAMING REQUEST - FIXED for all providers
    # -----------------------------------------------------------------
    async def _stream_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict,
        model_config: ModelConfig,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from API.
        
        FIXED ISSUES:
        1. ResponseNotRead: Don't call raise_for_status() inside stream context.
           Instead, read status manually and handle errors before iterating.
        2. Gemini SSE: Properly parse 'data: {...}' lines from alt=sse endpoint.
        3. Anthropic Events: Handle event: and data: line pairs correctly.
        4. Buffer partial JSON: Handle cases where JSON is split across chunks.
        """
        async with client.stream("POST", url, json=payload) as response:
            # ---- CHECK STATUS WITHOUT READING BODY ----
            # This is the key fix: response.raise_for_status() would try to read
            # the response body, causing ResponseNotRead error during streaming.
            if response.status_code == 401 or response.status_code == 403:
                # Read error body for auth errors
                error_body = ""
                async for chunk in response.aiter_bytes():
                    error_body += chunk.decode("utf-8", errors="replace")
                    if len(error_body) > 500:
                        break
                raise ProviderAuthError(model_config.provider, response.status_code, error_body)

            if response.status_code == 429:
                retry_after = float(response.headers.get("retry-after", "10"))
                # Read error body to distinguish quota exhaustion from rate limit
                error_body = ""
                try:
                    async for chunk in response.aiter_bytes():
                        error_body += chunk.decode("utf-8", errors="replace")
                        if len(error_body) > 1000:
                            break
                except Exception:
                    pass
                # Detect QUOTA EXHAUSTION (not retryable) vs RATE LIMIT (retryable)
                body_lower = error_body.lower()
                is_quota = any(kw in body_lower for kw in [
                    "quota", "resource_exhausted", "resource has been exhausted",
                    "exceeded your current quota", "rate_limit_exceeded",
                    "daily limit", "per-day", "per day",
                ])
                if is_quota:
                    raise ProviderQuotaExhausted(
                        model_config.provider, model_config.model_id, error_body[:300]
                    )
                raise ProviderRateLimit(model_config.provider, retry_after)

            if response.status_code >= 400:
                # Read the error response body
                error_body = ""
                async for chunk in response.aiter_bytes():
                    error_body += chunk.decode("utf-8", errors="replace")
                    if len(error_body) > 1000:
                        break
                raise ProviderAPIError(model_config.provider, response.status_code, error_body)

            # ---- STREAM THE RESPONSE ----
            provider = model_config.provider
            buffer = ""

            async for raw_line in response.aiter_lines():
                line = raw_line.strip()
                if not line:
                    continue

                # --- SSE format: "data: {json}" ---
                if line.startswith("data: "):
                    data_str = line[6:]

                    # OpenAI/Groq/DeepSeek/Together/OpenRouter: [DONE] signal
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data_str)
                        text = self._extract_stream_text(chunk_data, provider)
                        if text:
                            yield text
                    except json.JSONDecodeError:
                        # Might be partial JSON, accumulate in buffer
                        buffer += data_str
                        try:
                            chunk_data = json.loads(buffer)
                            text = self._extract_stream_text(chunk_data, provider)
                            if text:
                                yield text
                            buffer = ""
                        except json.JSONDecodeError:
                            continue

                # --- Anthropic event type lines ---
                elif line.startswith("event: "):
                    event_type = line[7:].strip()
                    # Anthropic sends event: message_stop when done
                    if event_type == "message_stop":
                        break
                    # Other events: message_start, content_block_start, 
                    # content_block_delta, content_block_stop, message_delta
                    continue

                # --- Raw JSON (some providers send without data: prefix) ---
                elif line.startswith("{"):
                    try:
                        chunk_data = json.loads(line)
                        text = self._extract_stream_text(chunk_data, provider)
                        if text:
                            yield text
                    except json.JSONDecodeError:
                        buffer += line
                        try:
                            chunk_data = json.loads(buffer)
                            text = self._extract_stream_text(chunk_data, provider)
                            if text:
                                yield text
                            buffer = ""
                        except json.JSONDecodeError:
                            continue

    # -----------------------------------------------------------------
    # TEXT EXTRACTION FROM STREAM CHUNKS
    # -----------------------------------------------------------------
    def _extract_stream_text(self, data: dict, provider: str) -> str:
        """Extract text from streaming response chunk for each provider."""
        try:
            if provider == "anthropic":
                # Anthropic sends different event types:
                # - content_block_delta: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "..."}}
                # - message_delta: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}
                msg_type = data.get("type", "")
                if msg_type == "content_block_delta":
                    delta = data.get("delta", {})
                    return delta.get("text", "")
                elif msg_type == "message_start":
                    # Sometimes the message_start contains initial content
                    return ""
                return ""

            elif provider == "gemini":
                # Gemini SSE format:
                # {"candidates": [{"content": {"parts": [{"text": "..."}]}, ...}]}
                # Thinking models may return parts with "thought": true
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        # Skip thinking parts (internal reasoning), only return text parts
                        for part in parts:
                            if part.get("thought"):
                                continue  # Skip thinking content
                            if "text" in part:
                                return part["text"]
                return ""

            else:  # OpenAI-compatible
                # {"choices": [{"delta": {"content": "..."}}]}
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    return delta.get("content", "") or ""
                return ""

        except (KeyError, IndexError, TypeError):
            return ""

    # -----------------------------------------------------------------
    # NON-STREAMING REQUEST
    # -----------------------------------------------------------------
    async def _simple_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict,
        model_config: ModelConfig,
    ) -> str:
        """Non-streaming request with proper error handling."""
        # Remove stream flag for non-streaming Gemini (different URL)
        if model_config.provider == "gemini":
            # For Gemini, the stream flag is in the URL, not the payload
            pass
        else:
            payload["stream"] = False

        response = await client.post(url, json=payload)

        # Handle errors
        if response.status_code == 401 or response.status_code == 403:
            raise ProviderAuthError(model_config.provider, response.status_code, response.text[:500])
        if response.status_code == 429:
            retry_after = float(response.headers.get("retry-after", "5"))
            body_lower = response.text.lower()
            is_quota = any(kw in body_lower for kw in [
                "quota", "resource_exhausted", "resource has been exhausted",
                "exceeded your current quota", "rate_limit_exceeded",
                "daily limit", "per-day", "per day",
            ])
            if is_quota:
                raise ProviderQuotaExhausted(
                    model_config.provider, model_config.model_id, response.text[:300]
                )
            raise ProviderRateLimit(model_config.provider, retry_after)
        if response.status_code >= 400:
            raise ProviderAPIError(model_config.provider, response.status_code, response.text[:500])

        data = response.json()

        if model_config.provider == "anthropic":
            content = data.get("content", [])
            if content:
                return content[0].get("text", "")
            return ""

        elif model_config.provider == "gemini":
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""

        else:  # OpenAI-compatible
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""

    # -----------------------------------------------------------------
    # TOKEN USAGE TRACKING
    # -----------------------------------------------------------------
    def _update_usage(self, model_config: ModelConfig, prompt: str, response: str):
        """Update token usage and cost tracking."""
        # Rough estimation: 1 token ~ 4 chars
        input_tokens = len(prompt) // 4
        output_tokens = len(response) // 4
        self.token_usage["input"] += input_tokens
        self.token_usage["output"] += output_tokens
        cost = (
            input_tokens / 1000 * model_config.cost_per_1k_input
            + output_tokens / 1000 * model_config.cost_per_1k_output
        )
        self.total_cost += cost

    # -----------------------------------------------------------------
    # ERROR FORMATTING
    # -----------------------------------------------------------------
    def _format_connection_error(self, model_config: ModelConfig) -> str:
        """Format a connection error with helpful hints based on provider."""
        provider = model_config.provider
        base_url = model_config.base_url

        hints = {
            "ollama": (
                f"\n\033[91m!! Cannot connect to Ollama at {base_url}\033[0m\n"
                f"\033[93m   Fix: Make sure Ollama is running:\033[0m\n"
                f"\033[93m     1. Install: curl -fsSL https://ollama.com/install.sh | sh\033[0m\n"
                f"\033[93m     2. Start:   ollama serve\033[0m\n"
                f"\033[93m     3. Pull:    ollama pull llama3.2\033[0m\n"
            ),
            "lmstudio": (
                f"\n\033[91m!! Cannot connect to LM Studio at {base_url}\033[0m\n"
                f"\033[93m   Fix: Open LM Studio and start the local server\033[0m\n"
                f"\033[93m     Settings > Local Server > Start Server\033[0m\n"
            ),
        }

        default = (
            f"\n\033[91m!! Connection failed to {provider} at {base_url}\033[0m\n"
            f"\033[93m   Fix: Check your internet connection\033[0m\n"
            f"\033[93m   Or verify the API URL: /model list\033[0m\n"
        )

        return hints.get(provider, default)

    # -----------------------------------------------------------------
    # CLEANUP
    # -----------------------------------------------------------------
    async def close(self):
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    def get_usage_stats(self) -> dict:
        return {
            "total_requests": self.request_count,
            "input_tokens": self.token_usage["input"],
            "output_tokens": self.token_usage["output"],
            "total_tokens": self.token_usage["input"] + self.token_usage["output"],
            "estimated_cost": f"${self.total_cost:.4f}",
            "errors": self.error_count,
            "last_error": self.last_error,
        }

    # -----------------------------------------------------------------
    # AUTO-FALLBACK: Find a working model when quota is exhausted
    # -----------------------------------------------------------------
    def _find_fallback_model(self, current_model_name: str, exhausted_model_id: str) -> Optional[str]:
        """Find another configured model from the same provider to fall back to.
        
        Returns the model name (key) or None if no fallback available.
        Priority order: gemini-2.5-flash > gemini-2.5-pro > others.
        """
        current = self.config.models.get(current_model_name)
        if not current:
            return None
        
        provider = current.provider
        
        # Check if there's already another model configured for this provider
        for name, cfg in self.config.models.items():
            if (name != current_model_name 
                and cfg.provider == provider 
                and cfg.model_id != exhausted_model_id
                and cfg.api_key
                and cfg.enabled):
                return name
        
        # No other model configured — try to auto-create one from DEFAULT_PROVIDERS
        from nexacode.config.settings import DEFAULT_PROVIDERS, ModelConfig
        provider_info = DEFAULT_PROVIDERS.get(provider, {})
        available = provider_info.get("models", [])
        base_url = provider_info.get("base_url", "")
        api_key = current.api_key
        
        # Preferred fallback order for Gemini
        preferred = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        candidates = [m for m in preferred if m in available and m != exhausted_model_id]
        # Add any remaining models not in preferred list
        candidates += [m for m in available if m not in candidates and m != exhausted_model_id]
        
        for model_id in candidates:
            # Fix: avoid double-prefix (gemini-gemini-2.5-flash)
            short_id = model_id.split('/')[-1]
            if short_id.startswith(provider):
                fallback_name = short_id
            else:
                fallback_name = f"{provider}-{short_id}"
            # Don't create if it already exists and was the current (exhausted) one
            if fallback_name in self.config.models:
                existing = self.config.models[fallback_name]
                if existing.model_id == exhausted_model_id:
                    continue
                # Ensure it has a valid API key (might be stale from disk)
                if not existing.api_key and api_key:
                    existing.api_key = api_key
                    self.config.save_config()
                return fallback_name
            
            # Auto-register the fallback model
            mc = ModelConfig(
                name=fallback_name,
                provider=provider,
                model_id=model_id,
                api_key=api_key,
                base_url=base_url,
            )
            self.config.add_model(fallback_name, mc)
            return fallback_name
        
        return None
