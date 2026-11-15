# Chrome and Edge companion

Build: `scripts/build_extension.sh`.

The distributable directory is `extension/dist`. It contains the popup, side panel, permission manifest, bundled React components, and URL/title symbol detector. It includes no credentials.

Manual acceptance, required by the CLI-only workspace rule:

1. Open `chrome://extensions` in Chrome, or `edge://extensions` in Edge. Enable Developer mode, choose **Load unpacked**, and select `/Users/harkiratkalra/harkirat/projects/finance/investors-eye/extension/dist`.
2. In the web workspace, open **Broker connections**, choose **Generate seven-day extension token**, and copy the token into the extension's pairing field. Keep it out of chat.
3. Use `http://127.0.0.1:8000` locally, or the configured HTTPS workspace origin remotely. Grant only that workspace's host permission when requested.
4. Verify that a saved instrument appears in the web watchlist, that the side panel opens, and that a created alert appears in the web account.
5. On supported Kite or Moneycontrol pages, click **Detect supported page symbol**. Detection reads URL and title only. It does not inspect forms or account data.
6. Choose **Unpair this session**. The token is revoked on the server and removed from extension session storage.

The build and API pairing are automated-test verified. Actual Chrome/Edge interaction and store review are not yet verified. Firefox is a separate compatibility release. Store publication needs the owner's developer account and privacy disclosures.
