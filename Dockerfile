# Gamitin ang medyo bago-bagong base image
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# 1. Install SSH Server
RUN apt-get update && apt-get install -y openssh-server

# 2. Setup SSH Password
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
# Force allow root login
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# 3. Setup App Folder
WORKDIR /app

# 4. Install Python Libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- MAGIC FIX: I-install ang tamang browser version ---
# Kahit mag-update ang Python library, ito ang magda-download ng tamang Chrome
RUN playwright install chromium
RUN playwright install-deps
# -------------------------------------------------------

# 5. Copy the Script
COPY scrape_wellfound_pro.py .

# 6. Start SSH
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
