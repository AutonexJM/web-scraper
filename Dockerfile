# Gamitin ang Image na may complete dependencies
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# 1. Override location: Sabihin sa Playwright na sa /root/.cache maglagay
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# 2. Install SSH
RUN apt-get update && apt-get install -y openssh-server

# 3. Setup SSH User
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# 4. App Setup
WORKDIR /app

# 5. Install Python Libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- THE FIX ---
# Dahil pinalitan natin ang PATH sa step 1,
# kapag nag-install tayo ngayon, mapupunta siya sa /root/.cache
# kung saan siya hinahanap ng script mo.
RUN playwright install chromium
RUN playwright install-deps
# ---------------

# 6. Copy Script & Start
COPY scrape_wellfound_pro.py .
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
