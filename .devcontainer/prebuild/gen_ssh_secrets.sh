# Generate RSA key pair for user
ssh-keygen -t rsa -b 4096 -f user_key -N ""
echo "\n" >> ~/.bashrc
echo "export TF_VAR_ssh_key_public_user='$(cat user_key.pub)'" >> ~/.bashrc
echo "export TF_VAR_ssh_key_private_user='$(cat user_key)'" >> ~/.bashrc
rm user_key user_key.pub

# Generate RSA key pair for admin
ssh-keygen -t rsa -b 4096 -f admin_key -N ""
echo "export TF_VAR_ssh_key_public_admin='$(cat admin_key.pub)'" >> ~/.bashrc
echo "export TF_VAR_ssh_key_private_admin='$(cat admin_key)'" >> ~/.bashrc
rm admin_key admin_key.pub
