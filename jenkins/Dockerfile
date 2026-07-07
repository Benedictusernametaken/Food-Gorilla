# Extends the official Jenkins image to add Ansible, which the base
# jenkins/jenkins:lts-jdk17 image does not ship with. Without this, Stage 4
# ("Deploy Application via Ansible") fails with "ansible-playbook: command
# not found" — even once a real playbook and hosts.ini exist — because
# pipeline steps with `agent any` run directly inside this container.
FROM jenkins/jenkins:lts-jdk17

USER root

# ansible-core via apt keeps this lightweight and avoids needing pip/venv
# management inside the Jenkins container just for one tool.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ansible && \
    rm -rf /var/lib/apt/lists/*

USER jenkins