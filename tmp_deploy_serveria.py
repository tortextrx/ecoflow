import paramiko
from pathlib import Path

HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    sftp = client.open_sftp()
    
    # Backup
    print("Creating remote backup...")
    client.exec_command("tar -czf /home/ecoflow/app_backup_auth_$(date +%Y%m%d_%H%M%S).tar.gz /home/ecoflow/app")
    
    # Mkdir
    client.exec_command("mkdir -p /home/ecoflow/app/security")
    
    # Env Variables Update
    print("Configuring environment variables in /home/ecoflow/.env...")
    env_cmds = """
grep -q '^ECOSOFT_TOKEN_AUTH=' /home/ecoflow/.env || echo 'ECOSOFT_TOKEN_AUTH=' >> /home/ecoflow/.env
sed -i "s|^ECOSOFT_TOKEN_AUTH=.*|ECOSOFT_TOKEN_AUTH=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9|" /home/ecoflow/.env

grep -q '^ECOFLOW_DEV_BEARER=' /home/ecoflow/.env || echo 'ECOFLOW_DEV_BEARER=' >> /home/ecoflow/.env
sed -i "s|^ECOFLOW_DEV_BEARER=.*|ECOFLOW_DEV_BEARER=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.lUpN8au+eneOkQ4IgVup8Q==|" /home/ecoflow/.env

grep -q '^ECOFLOW_ALLOW_DEV_BEARER_FALLBACK=' /home/ecoflow/.env || echo 'ECOFLOW_ALLOW_DEV_BEARER_FALLBACK=' >> /home/ecoflow/.env
sed -i "s|^ECOFLOW_ALLOW_DEV_BEARER_FALLBACK=.*|ECOFLOW_ALLOW_DEV_BEARER_FALLBACK=true|" /home/ecoflow/.env
"""
    client.exec_command(env_cmds)
    
    for local, remote in [
        ('app/api/routes_chat.py', '/home/ecoflow/app/api/routes_chat.py'),
        ('app/core/config.py', '/home/ecoflow/app/core/config.py'),
        ('app/security/__init__.py', '/home/ecoflow/app/security/__init__.py'),
        ('app/security/bearer_context.py', '/home/ecoflow/app/security/bearer_context.py')
    ]:
        print(f"Syncing {local} to {remote}...")
        sftp.put(local, remote)
    
    sftp.close()
    
    print("Restarting ecoflow service...")
    stdin, stdout, stderr = client.exec_command("systemctl restart ecoflow")
    print(stdout.read().decode())
    print(stderr.read().decode())
    
    # Check status
    stdin, stdout, stderr = client.exec_command("systemctl is-active ecoflow")
    status = stdout.read().decode().strip()
    print(f"Service status: {status}")
    
    if status == 'active':
        print("Final Deployment SUCCESS")
    else:
        print("Warning: Service is not active after restart")
        
    client.close()
except Exception as e:
    print(f"Deployment failed: {e}")

