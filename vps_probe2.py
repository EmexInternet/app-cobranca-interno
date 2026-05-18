import os, paramiko
host='89.117.32.226'; user='root'; password=os.environ['SAASTV_VPS_PASSWORD']
cmd=r'''echo '---USERS---'; cut -d: -f1,6 /etc/passwd | tail -20; echo '---CRON DIRS---'; ls -la /etc/cron.d /var/spool/cron/crontabs 2>/dev/null || true; echo '---CRON GREP---'; grep -RniE 'cobranca|app_python_automacao|python -m app_python_automacao' /etc/cron* /var/spool/cron 2>/dev/null || true; echo '---FIND APP---'; find / -type d -name 'app-cobranca-backend' 2>/dev/null | head -20; echo '---FIND LOG---'; find / -type f \( -name 'app-cobranca-backend.log' -o -name '*cobranca*.log' \) 2>/dev/null | head -40'''
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()); ssh.connect(host, username=user, password=password, timeout=20)
_, stdout, stderr=ssh.exec_command(cmd, timeout=120)
print(stdout.read().decode()); err=stderr.read().decode(); print(err)
ssh.close()
