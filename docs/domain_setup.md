# Domain Setup Guide (connecting game.pixek.xyz)

This guide explains how to point your domain to your Oracle Cloud server and fix the Google Login restriction.

## 1. DNS Configuration (Domain Provider)
Go to your domain registrar (where you bought `pixek.xyz`) or your DNS provider (like Cloudflare):

1.  Find the **DNS Management** or **Advanced DNS** settings for `pixek.xyz`.
2.  Click **Add New Record**.
3.  Choose **Type**: `A`
4.  Set **Host**: `game` (this creates `game.pixek.xyz`).
5.  Set **Value/Address**: `92.5.113.36`
6.  Set **TTL**: `Automatic` or `1 Hour`.
7.  **Save** the record.

> [!NOTE] 
> It can take from 5 minutes to a few hours for the world to "learn" that `game.pixek.xyz` now points to your server.

## 2. Update Google Cloud Console
Now that you have a domain, Google will allow it in your login settings:

1.  Go to the [Google Cloud Console Credentials Page](https://console.cloud.google.com/apis/credentials).
2.  Click on your **OAuth 2.0 Client ID** (the one used for this project).
3.  Under **Authorized JavaScript origins**, click **+ ADD URI**.
4.  Add your new address: `http://game.pixek.xyz:3000`
5.  Under **Authorized redirect URIs**, click **+ ADD URI**.
6.  Add: `http://game.pixek.xyz:3000`
7.  Click **Save**.

## 3. (Optional) Remove the :3000 from the URL
If you want users to just type `game.pixek.xyz` (without the `:3000` at the end), follow these steps on your Oracle Server:

1.  **Edit the configuration**:
    ```bash
    cd ~/Project-Autonomous-Frontier
    nano docker-compose.yml
    ```
2.  Find the `backend` section and change the `ports` mapping for 3000 to **80**:
    ```yaml
    ports:
      - "80:8000"  # Change this from 3000:8000
      - "8000:8000"
    ```
3.  Save (`CTRL+O`, `Enter`) and Exit (`CTRL+X`).
4.  **Open Port 80 in Oracle Cloud**:
    - Go back to your **Security List** in the Oracle Console.
    - Add an **Ingress Rule** for Port **80** (Source CIDR: `0.0.0.0/0`, Protocol: `TCP`).
5.  **Restart the server**:
    ```bash
    sudo docker-compose up -d
    ```
6.  **Update Google Settings**: Change your origins in Google Console to `http://game.pixek.xyz` (removing the `:3000`).

---

### Verify Setup
You can verify if the domain is correctly pointed by using this command in your Windows PowerShell:
`nslookup game.pixek.xyz`

If it returns `92.5.113.36`, you are ready!
