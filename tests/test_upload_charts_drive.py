import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch, sentinel

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'upload-charts-drive.py'
spec = importlib.util.spec_from_file_location('upload_charts_drive', SCRIPT)
assert spec is not None and spec.loader is not None
upload_charts_drive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload_charts_drive)


def test_force_reauth_ignores_cached_token_and_replaces_it(tmp_path: Path) -> None:
    credentials_path = tmp_path / 'credentials.json'
    credentials_path.touch()
    token_path = tmp_path / 'token.json'
    token_path.write_text('old token', encoding='utf-8')
    credentials = Mock(valid=True)
    credentials.to_json.return_value = 'new token'
    flow = Mock()
    flow.run_local_server.return_value = credentials

    with (
        patch.object(upload_charts_drive.Credentials, 'from_authorized_user_file') as load_token,
        patch.object(
            upload_charts_drive.InstalledAppFlow,
            'from_client_secrets_file',
            return_value=flow,
        ),
    ):
        result = upload_charts_drive.authenticate(
            credentials_path, token_path, port=0, open_browser=False, force_reauth=True
        )

    load_token.assert_not_called()
    flow.run_local_server.assert_called_once_with(port=0, open_browser=False)
    assert result is credentials
    assert token_path.read_text(encoding='utf-8') == 'new token'


def test_auth_only_does_not_upload(tmp_path: Path) -> None:
    token_path = tmp_path / 'token.json'
    token_path.touch()
    with (
        patch.object(upload_charts_drive, 'authenticate', return_value=sentinel.credentials),
        patch.object(upload_charts_drive, 'build') as build_service,
        patch.object(upload_charts_drive, 'upload_charts') as upload,
    ):
        upload_charts_drive.main(['--token', str(token_path), '--reauth', '--auth-only'])

    build_service.assert_not_called()
    upload.assert_not_called()
