
cd /workspace/.deployment/tofu
tofu refresh
export sftp_admin_username="$(tofu output sftp_admin_username)"
export sftp_server_endpoint="$(tofu output sftp_server_endpoint)"
echo "# TOFU ENV VARS" >> ~/.bashrc
echo "SFTP_ADMIN_USERNAME=$sftp_admin_username" >> ~/.bashrc
echo "SFTP_SERVER_ENDPOINT=$sftp_server_endpoint" >> ~/.bashrc
