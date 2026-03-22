
import paramiko
from pathlib import Path

HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'

files_to_deploy = {
    'app/main.py': '/home/ecoflow/app/main.py',
    'app/static/index.html': '/home/ecoflow/app/static/index.html'
}

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    sftp = client.open_sftp()

    for local, remote in files_to_deploy.items():
        with open(local, 'r', encoding='utf-8') as f:
            content = f.read()
        with sftp.file(remote, 'w') as sf:
            sf.write(content)
        print(f"Uploaded: {local} -> {remote}")

    sftp.close()
    
    # Restart Service
    print("Restarting ecoflow service...")
    stdin, stdout, stderr = client.exec_command('systemctl restart ecoflow')
    exit_status = stdout.channel.recv_exit_status()
    
    if exit_status == 0:
        print("Service Restart OK")
    else:
        print(f"Service Restart Failed: {stderr.read().decode()}")

    client.close()
    print("Nginx Bypass Deploy OK")

except Exception as e:
    print(f"Error: {e}")
