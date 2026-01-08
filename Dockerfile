# Gamitin ang match na version (v1.49.0)
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# --- THE MISSING KEY: THE MAP ---
# Sabihin natin sa script: "Wag ka sa /root/.cache humanap. Dito ka sa /ms-playwright tumingin."
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
# --------------------------------

# 1. Install SSH
RUN apt-get update && apt-get install -y openssh-server

# 2. Setup SSH User
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# 3. App Setup
WORKDIR /app

# 4. Install Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# (Hindi na kailangan mag 'RUN playwright install' kasi ituturo na lang natin yung existing)

# 5. Copy Script & Start
COPY scrape_wellfound_pro.py .
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
