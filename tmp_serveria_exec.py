import argparse
import json
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")


def run_remote(command: str) -> dict:
    host = "10.20.167.5"
    user = "root"
    password = "o1wrNtxq2?fA"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password, timeout=30)
    try:
        stdin, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return {"exit_code": code, "stdout": out, "stderr": err, "command": command}
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="Comando remoto único a ejecutar")
    args = parser.parse_args()
    result = run_remote(args.command)
    print(json.dumps(result, ensure_ascii=False))
