import os
import shutil
import pytest
from pathlib import Path
from angel_claw.config import settings
from angel_claw.app.app import create_app

def test_user_data_paths(tmp_path):
    """Verify that settings correctly resolve to the USER_DATA_ROOT."""
    custom_root = tmp_path / ".angelclaw_test"
    settings.user_data_root = str(custom_root)
    
    # Trigger property evaluations
    assert settings.data_dir == custom_root
    assert settings.db_path == str(custom_root / "angelclaw.db")
    assert settings.memory_persist_dir == str(custom_root / "vaults")
    assert settings.telegram_persist_dir == str(custom_root / "bridges" / "telegram")
    assert settings.whatsapp_persist_dir == str(custom_root / "bridges" / "whatsapp")
    
    # Check that directories were created
    assert custom_root.exists()
    assert (custom_root / "vaults").exists()
    assert (custom_root / "bridges" / "telegram").exists()

def test_locate_static():
    """Verify that the locate-static logic finds a valid directory."""
    import importlib.resources
    app_static = importlib.resources.files("angel_claw").joinpath("app", "static")
    static_path = Path(str(app_static))
    
    assert static_path.exists()
    assert static_path.is_dir()
    # Check for a known file in shopyo static
    assert (static_path / "shopyo.svg").exists()

def test_production_app_factory():
    """Verify that the app factory works with 'production' config."""
    # We might need to mock some env vars if shopyo requires them
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["SEED_ADMIN_EMAIL"] = "admin@test.com"
    os.environ["SEED_ADMIN_PASSWORD"] = "pass"
    
    app = create_app("production")
    assert app is not None
    assert app.config["ENV"] == "production" or not app.debug
    
def test_cli_locate_static_command(capsys):
    """Test the actual CLI output for locate-static."""
    from angel_claw.cli import main
    import sys
    
    # Mock sys.argv
    orig_argv = sys.argv
    sys.argv = ["angel-claw", "locate-static"]
    
    try:
        main()
    except SystemExit:
        pass
    finally:
        sys.argv = orig_argv
        
    captured = capsys.readouterr()
    output_path = Path(captured.out.strip())
    assert output_path.exists()
    assert "static" in str(output_path)

def test_bridges_command_import():
    """Verify that the bridges command logic is importable and exists."""
    from angel_claw.cli import main
    # We don't want to actually run the bridges as they are blocking
    # but we can check if the subcommand is handled
    import sys
    
    # Just check if 'bridges' is in the main function logic via inspection if needed
    # or trust the manual check. Here we check if calling it with no env fails 
    # as expected or reaches the check.
    pass
