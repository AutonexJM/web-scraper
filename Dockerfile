# 1. Gamit tayo ng standard Python image (Malinis)
FROM python:3.9-slim

# 2. Install SSH at iba pang tools na kailangan ng Chrome
RUN apt-get update && apt-get install -y \
    openssh-server \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Setup SSH User & Password
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# 4. Setup App Folder
WORKDIR /app

# 5. Install Python Libraries (Dito i-install ang Latest Playwright)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. --- MAGIC PART: Install Browsers ---
# Dahil fresh install, siguradong match ang Browser sa Playwright Version
RUN playwright install chromium
RUN playwright install-deps
# -------------------------------------

# 7. Copy Script & Start
COPY scrape_wellfound_pro.py .
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
