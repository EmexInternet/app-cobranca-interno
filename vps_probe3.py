import os, paramiko
host='89.117.32.226'; user='root'; password=os.environ['SAASTV_VPS_PASSWORD']
cmd=r'''echo '---FIND PY PROJECT---'; find /root /home /opt /srv -type f \( -name 'workflow.py' -o -name 'cli.py' -o -name '.env' \) 2>/dev/null | grep -E 'cobranca|automacao' | head -80; echo '---PROCESS GREP---'; ps aux | grep -Ei 'cobranca|app_python_automacao' | grep -v grep || true; echo '---JOURNAL GREP---'; journalctl --since '2026-05-17' --no-pager 2>/dev/null | grep -Ei 'cobranca|app_python_automacao' | tail -80 || true'''
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()); ssh.connect(host, username=user, password=password, timeout=20)
_, stdout, stderr=ssh.exec_command(cmd, timeout=120)
print(stdout.read().decode()); err=stderr.read().decode(); print(err)
ssh.close()
