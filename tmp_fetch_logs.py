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
    
    sftp.get('/tmp/eco_logs.txt', 'eco_logs_local.txt')
    
    sftp.close()
    client.close()
    print("Logs downloaded successfully.")
except Exception as e:
    print(f"Error: {e}")
