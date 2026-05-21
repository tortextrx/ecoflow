import paramiko

HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'

FILES = [
    ('app/core/config.py', '/home/ecoflow/app/core/config.py'),
    ('app/security/bearer_context.py', '/home/ecoflow/app/security/bearer_context.py'),
    ('app/api/routes_chat.py', '/home/ecoflow/app/api/routes_chat.py'),
    ('app/connectors/base.py', '/home/ecoflow/app/connectors/base.py'),
    ('app/static/chat.js', '/home/ecoflow/app/static/chat.js'),
    ('app/static/index.html', '/home/ecoflow/app/static/index.html'),
    ('docs/ECOFLOW_PRODUCTION_INTEGRATION.md', '/home/ecoflow/docs/ECOFLOW_PRODUCTION_INTEGRATION.md')
]

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    sftp = client.open_sftp()
    
    print("Creating remote backup...")
    client.exec_command("tar -czf /home/ecoflow/app_backup_v5_security_$(date +%Y%m%d_%H%M%S).tar.gz /home/ecoflow/app")
    
    # Configure .env
    # We remove old vars and add new ones
    print("Updating .env configuration...")
    env_cmds = """
sed -i '/ECOSOFT_TOKEN_AUTH/d' /home/ecoflow/.env
sed -i '/ECOSOFT_TOKEN_USUARIO/d' /home/ecoflow/.env
sed -i '/ECOFLOW_DEV_BEARER/d' /home/ecoflow/.env
sed -i '/ECOFLOW_ALLOW_DEV_BEARER_FALLBACK/d' /home/ecoflow/.env

grep -q 'ECOFLOW_SECURITY_TOKEN' /home/ecoflow/.env || echo 'ECOFLOW_SECURITY_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' >> /home/ecoflow/.env
grep -q 'ECOFLOW_INTERNAL_CHAT_ALLOW_DEMO_ERP_TOKEN' /home/ecoflow/.env || echo 'ECOFLOW_INTERNAL_CHAT_ALLOW_DEMO_ERP_TOKEN=true' >> /home/ecoflow/.env
grep -q 'ECOFLOW_INTERNAL_CHAT_DEMO_ERP_TOKEN' /home/ecoflow/.env || echo 'ECOFLOW_INTERNAL_CHAT_DEMO_ERP_TOKEN=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.lUpN8au+eneOkQ4IgVup8Q==' >> /home/ecoflow/.env
"""
    client.exec_command(env_cmds)

    for local, remote in FILES:
        print(f"Syncing {local} to {remote}...")
        sftp.put(local, remote)
    
    sftp.close()
    
    print("Restarting ecoflow service...")
    client.exec_command("systemctl restart ecoflow")
    
    print("Deployment finished successfully.")
    client.close()
except Exception as e:
    print(f"Deployment failed: {e}")
