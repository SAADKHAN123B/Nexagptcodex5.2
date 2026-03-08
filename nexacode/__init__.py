"""NexaCode -- AI-Powered Terminal Coding Assistant"""

from nexacode.config.settings import APP_NAME, APP_VERSION, APP_CODENAME

__version__ = APP_VERSION
__app_name__ = APP_NAME
__codename__ = APP_CODENAME


def entry_point():
    """CLI entry point."""
    import sys
    import asyncio
    from pathlib import Path
    
    # Ensure parent dir is in path
    script_dir = Path(__file__).parent.parent.resolve()
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    
    # Import and run main from nexacode.py 
    import importlib
    main_module = importlib.import_module("nexacode")
    if hasattr(main_module, 'entry_point'):
        main_module.entry_point()


# Make sub-packages importable
try:
    from nexacode import core, agents, tools, db, ui, config, utils
except ImportError:
    pass
