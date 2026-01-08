# Gamitin ang v1.49.0 para match sa requirements
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# 1. Install SSH
RUN apt-get update && apt-get install -y openssh-server

# 2. Setup SSH User
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# 3. Setup App
WORKDIR /app

# 4. Install Libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- THE UNIVERSAL FIX ---
# Ito ang kulang kanina. Pipilitin nating lagyan ng browser
# kung saan siya hinahanap ng script (sa /root/.cache).
RUN playwright install chromium
RUN playwright install-deps
# -------------------------

# 5. Copy Script & Start
COPY scrape_wellfound_pro.py .
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
