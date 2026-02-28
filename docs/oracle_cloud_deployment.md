# Terminal Frontier - Oracle Cloud Deployment Guide

This guide is for complete beginners who want to host their own Terminal Frontier server forever for free using Oracle Cloud Infrastructure (OCI).

## 1. Create an Oracle Cloud Account
1. Go to [oracle.com/cloud/free/](https://oracle.com/cloud/free/) and sign up.
2. You will need a credit card for identity verification, but you won't be charged if you stay within the "Always Free" limits.
3. Choose a **Home Region** close to you (e.g., US East, Germany Central).

## 2. Create your "Always Free" Instance
1. In the OCI Console, go to **Compute** -> **Instances** -> **Create Instance**.
2. **Name**: `terminal-frontier-server`
3. **Placement**: Leave as default.
4. **Image and Shape**:
    - Click **Edit** in the **Image and Shape** section.
    - Click **Change Image**.
    - Select **Canonical Ubuntu** (Version 22.04 or 24.04). This is the most beginner-friendly and fits all instructions in this guide.
    - Click **Select Image**.
    - Click **Change Shape**.
    - Select **Ampere (ARM based processor)**.
    - Choose **VM.Standard.A1.Flex**.
    - **OCPUs**: 1 or 2.
    - **Memory**: 6GB - 12GB (Always Free covers up to 4 OCPUs and 24GB total).
5. **Networking**: Keep default VCN and public IP.
6. **SSH Keys**:
    - Click **Save Private Key** (download it to your computer, e.g., `ssh-key.key`).
7. **Create** the instance.

## 3. Configure the Network (Firewall)
You need to open ports so people can play.
1. On the Instance page, click on the **Subnet** name.
2. Click on the **Default Security List**.
3. Click **Add Ingress Rules**.
4. Add the following rule for the Frontend (Web UI):
    - **Source CIDR**: `0.0.0.0/0`
    - **IP Protocol**: `TCP`
    - **Destination Port Range**: `3000`
5. Add another rule for the Backend (API):
    - **Source CIDR**: `0.0.0.0/0`
    - **IP Protocol**: `TCP`
    - **Destination Port Range**: `8000`

## 4. Setup the Server (Terminal)
1. Find your **Public IP Address** on the Instance page.
2. Open your terminal (PowerShell on Windows, Terminal on Mac/Linux).
3. Connect using your key:
   ```bash
   ssh -i ssh-key.key ubuntu@YOUR_PUBLIC_IP
   ```
4. Install Docker:
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose
   sudo usermod -aG docker ubuntu
   # Enable modern BuildKit for faster builds
   echo "export DOCKER_BUILDKIT=1" >> ~/.bashrc
   echo "export COMPOSE_DOCKER_CLI_BUILD=1" >> ~/.bashrc
   # Log out and log back in for docker permissions to apply
   exit
   ssh -i ssh-key.key ubuntu@YOUR_PUBLIC_IP
   ```

## 5. Deploy the Game
1. Clone your repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Terminal-Frontier.git
   cd Terminal-Frontier
   ```
2. Start the game:
   ```bash
   docker-compose up -d
   ```
   *This will start the database (Postgres), the backend, and the frontend automatically.*

## 6. How to Update
When you make changes to your code and push them to GitHub:
1. Connect to your server via SSH.
2. Pull the latest code:
   ```bash
   cd Project-Autonomous-Frontier
   git pull
   ```
3. Rebuild and restart:
   ```bash
   docker-compose up -d --build
   ```
   if it's already running do this first to stop it: 
   sudo docker-compose down


## Persistence Notes
- Your data is stored in the `postgres_data` volume defined in `docker-compose.yml`. Even if you restart the server, the database remains intact.
- The "Tick" will resume from where it left off automatically.
- Avoid using `run_demo.py` on the cloud server, as it is designed for temporary local testing and resets the database.

> [!TIP]
> To see the logs of your server, run: `docker-compose logs -f backend`

## 7. Troubleshooting & Best Practices

### A. Database Migrations (Schema Changes)
Whenever a new feature adds columns to the database (like Rarity or Affixes), the live server will crash with a `500 Internal Server Error` until the database is updated.
1. **Pull the code**: `git pull`
2. **Run migration**: `docker-compose exec backend python migrate.py`
3. **Check Output**: If the migration script says "Column already exists", that's normal. If it says "Successfully handled", the fix is applied.

### B. Monitoring Logs
If the website isn't loading data, the backend logs are the first place to look.
- **View logs**: `docker-compose logs --tail=50 -f backend`
- **Look for**: `CRITICAL`, `ERROR`, or Python tracebacks.
- **Unbuffered Output**: If you don't see logs immediately, try running the command with `python -u`.

### C. Resource Lock-ups
On low-resource (Always Free) instances, the database or backend might occasionally hang.
- **Full Restart**: `docker-compose down && docker-compose up -d --build`
- **Prune old data**: `docker system prune` (Only if disk is full).

### D. Google OAuth Whitelisting
If you change your server's domain or IP address, you **must** update the Google Cloud Console.
1. Go to **APIs & Services** -> **Credentials**.
2. Edit your **OAuth 2.0 Client ID**.
3. Add your IP with port 3000 (e.g., `http://92.5.113.36:3000`) to **Authorized JavaScript origins**.

### E. Defensive Coding
- Check for `None` values when accessing optional JSON fields.
- Always add a default fallback when `getattr()` or `get()` is used on database objects.
- Use `try...except` in middlewares to log exact error locations before the 500 response is sent.

## 8. Performance Tuning for Small Instances

If your server is slow or non-responsive, try these adjustments:

### A. SQLite Performance (WAL Mode)
The latest backend version automatically enables **WAL Mode** (Write-Ahead Logging). This allows multiple readers to coexist with a writer, significantly reducing "Database locked" errors.

### B. Uvicorn Workers
On a 1-core Arm instance, multiple workers can sometimes cause context-switching overhead. 
- Edit `docker-compose.yml` (if you are using multiple workers) to use only **1 worker** but increase concurrency.
- Command example: `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --limit-concurrency 500`

### C. Heartbeat Synchronization
The game simulation runs on a 20s cycle. Ensure your frontend is not polling too aggressively. 
- The default poll rate is set to **5s**. Do not set it lower than **2s**.

### D. Docker Resource Limits
You can limit the resources for the backend container in `docker-compose.yml` to prevent it from hogging the entire system:
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 512M
```
