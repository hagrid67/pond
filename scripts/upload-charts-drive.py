#!/usr/bin/env python3
"""Authenticate with Google Drive and upload chart PNGs from ./charts.

Default target:
  Parent folder: SwimForum-2026 (1ES43t99ghz8EaoWF5vw2CuRtVwrf0zFM)
  Subfolder:     charts (created automatically if it does not exist)
"""

import argparse
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

DEFAULT_PARENT_FOLDER_ID = '1ES43t99ghz8EaoWF5vw2CuRtVwrf0zFM'
DEFAULT_SUBFOLDER_NAME = 'charts'
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'


def extract_folder_id(folder_id_or_url: str) -> str:
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', folder_id_or_url)
    if match:
        return match.group(1)
    return folder_id_or_url.strip()


def resolve_default_credentials_path(repo_root: Path) -> Path:
    local_cred = repo_root / 'keys' / 'google-credentials.json'
    if local_cred.exists():
        return local_cred
    hmpa_cred = repo_root.parent / 'hmpa' / 'google' / 'credentials.json'
    if hmpa_cred.exists():
        return hmpa_cred
    return local_cred


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description='Upload PNG charts from ./charts into a Google Drive folder.'
    )
    parser.add_argument(
        '--parent-folder',
        default=DEFAULT_PARENT_FOLDER_ID,
        help=(
            'Google Drive parent folder ID or URL '
            f'(default: {DEFAULT_PARENT_FOLDER_ID} / SwimForum-2026).'
        ),
    )
    parser.add_argument(
        '--subfolder',
        default=DEFAULT_SUBFOLDER_NAME,
        help=f'Subfolder name inside the parent Drive folder (default: {DEFAULT_SUBFOLDER_NAME}).',
    )
    parser.add_argument(
        '--charts-dir',
        type=Path,
        default=repo_root / 'charts',
        help='Local directory containing chart PNGs (default: ./charts).',
    )
    parser.add_argument(
        '--credentials',
        type=Path,
        default=resolve_default_credentials_path(repo_root),
        help='Path to Google OAuth client secrets JSON file.',
    )
    parser.add_argument(
        '--token',
        type=Path,
        default=repo_root / 'keys' / 'google-drive-token.json',
        help='Path to cached Google Drive OAuth token JSON file.',
    )
    parser.add_argument(
        '--port',
        type=int,
        default=0,
        help='Local port for the OAuth callback server (default: 0, auto-select).',
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Print the OAuth authorization URL without automatically launching a browser.',
    )
    return parser.parse_args(argv)


def authenticate(
    credentials_path: Path, token_path: Path, port: int, open_browser: bool = True
) -> Credentials:
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f'Google OAuth client credentials file not found at {credentials_path}. '
                    'Pass --credentials /path/to/credentials.json or place it at '
                    'keys/google-credentials.json.'
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=port, open_browser=open_browser)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding='utf-8')

    return creds


def ensure_drive_subfolder(service, parent_id: str, subfolder_name: str) -> str:
    escaped_name = subfolder_name.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents "
        f"and name = '{escaped_name}' "
        f"and mimeType = '{FOLDER_MIME_TYPE}' "
        "and trashed = false"
    )
    response = (
        service.files()
        .list(
            q=query,
            spaces='drive',
            fields='files(id, name, webViewLink)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = response.get('files', [])
    if files:
        folder = files[0]
        print(f"Found existing Drive folder '{subfolder_name}' ({folder['id']})")
        return folder['id']

    metadata = {
        'name': subfolder_name,
        'mimeType': FOLDER_MIME_TYPE,
        'parents': [parent_id],
    }
    created = (
        service.files()
        .create(
            body=metadata,
            fields='id, name, webViewLink',
            supportsAllDrives=True,
        )
        .execute()
    )
    print(f"Created Drive folder '{subfolder_name}' ({created['id']})")
    return created['id']


def list_existing_files_in_folder(service, folder_id: str) -> dict[str, str]:
    query = f"'{folder_id}' in parents and trashed = false"
    response = (
        service.files()
        .list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=200,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    return {item['name']: item['id'] for item in response.get('files', [])}


def upload_charts(
    service,
    charts_dir: Path,
    parent_folder_id: str,
    subfolder_name: str,
    files: list[Path] | None = None,
) -> list[dict[str, str]]:
    png_files = list(files) if files is not None else sorted(charts_dir.glob('*.png'))
    if not png_files:
        raise FileNotFoundError(f'No .png files found in {charts_dir}')

    target_folder_id = (
         ensure_drive_subfolder(service, parent_folder_id, subfolder_name)
        if subfolder_name
        else parent_folder_id
    )
    existing = list_existing_files_in_folder(service, target_folder_id)
    uploaded: list[dict[str, str]] = []

    for png_path in png_files:
        media = MediaFileUpload(str(png_path), mimetype='image/png', resumable=False)
        if png_path.name in existing:
            file_id = existing[png_path.name]
            result = (
                service.files()
                .update(
                    fileId=file_id,
                    media_body=media,
                    fields='id, name, webViewLink',
                    supportsAllDrives=True,
                )
                .execute()
            )
            action = 'Updated'
        else:
            metadata = {'name': png_path.name, 'parents': [target_folder_id]}
            result = (
                service.files()
                .create(
                    body=metadata,
                    media_body=media,
                    fields='id, name, webViewLink',
                    supportsAllDrives=True,
                )
                .execute()
            )
            action = 'Uploaded'

        print(f"{action} {result['name']} -> {result.get('webViewLink', result['id'])}")
        uploaded.append(result)

    print(
        f"\nCompleted uploading {len(uploaded)} chart(s) to "
        f"https://drive.google.com/drive/folders/{target_folder_id}"
    )
    return uploaded


def upload_chart_files(
    files: list[Path],
    parent_folder_id: str = DEFAULT_PARENT_FOLDER_ID,
    subfolder_name: str = DEFAULT_SUBFOLDER_NAME,
) -> list[dict[str, str]]:
    repo_root = Path(__file__).resolve().parent.parent
    creds = authenticate(
        credentials_path=resolve_default_credentials_path(repo_root),
        token_path=repo_root / 'keys' / 'google-drive-token.json',
        port=0,
        open_browser=True,
    )
    service = build('drive', 'v3', credentials=creds)
    return upload_charts(
        service=service,
        charts_dir=repo_root / 'charts',
        parent_folder_id=extract_folder_id(parent_folder_id),
        subfolder_name=subfolder_name,
        files=files,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    parent_folder_id = extract_folder_id(args.parent_folder)
    creds = authenticate(
        args.credentials,
        args.token,
        args.port,
        open_browser=not args.no_browser,
    )
    service = build('drive', 'v3', credentials=creds)
    upload_charts(
        service=service,
        charts_dir=args.charts_dir,
        parent_folder_id=parent_folder_id,
        subfolder_name=args.subfolder,
    )


if __name__ == '__main__':
    main()
