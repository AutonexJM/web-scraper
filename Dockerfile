FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Override location
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Install SSH
RUN apt-get update && apt-get install -y openssh-server

# Setup User
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

WORKDIR /app

# Install Libraries (Kasama na ang stealth)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Force Browser Install
RUN playwright install chromium
RUN playwright install-deps

COPY scrape_wellfound_pro.py .
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]

# ... (ibang commands sa taas)

# 4. Install Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- FIX: Install Browsers ---
RUN playwright install chromium
RUN playwright install-deps
# -----------------------------

# 5. COPY ALL SCRIPTS (Ito ang pagbabago)
# Kopyahin lahat ng files sa folder papunta sa container
COPY . .

# 6. Start SSH
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
