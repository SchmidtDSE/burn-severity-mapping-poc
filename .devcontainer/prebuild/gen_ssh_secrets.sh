# Generate RSA key pair for user
ssh-keygen -t rsa -b 4096 -f user_key -N ""

# Generate RSA key pair for admin
ssh-keygen -t rsa -b 4096 -f admin_key -N ""


# Save public and private keys as a list of JSON objects
# Create an array to store the key-value pairs
keys=()

# Add the user key pair to the array
user_public_key=$(cat user_key.pub)
user_private_key=$(cat user_key)
keys+=("\"SSH_KEY_USER_PUBLIC\": \"$user_public_key\"")
keys+=("\"SSH_KEY_USER_PRIVATE\": \"${user_private_key//$'\n'/\\n}\"")

# Add the admin key pair to the array
admin_public_key=$(cat admin_key.pub)
admin_private_key=$(cat admin_key)
keys+=("\"SSH_KEY_ADMIN_PUBLIC\": \"$admin_public_key\"")
keys+=("\"SSH_KEY_ADMIN_PRIVATE\": \"${admin_private_key//$'\n'/\\n}\"")

# Convert the array to JSON and save it to a file
echo '{' > ssh_keys.json
for ((i=0; i<${#keys[@]}; i++)); do
    echo "${keys[i]}" >> ssh_keys.json
    if [[ $i -lt $((${#keys[@]}-1)) ]]; then
        echo ',' >> ssh_keys.json
    fi
done
echo '}' >> ssh_keys.json

# Use the AWS CLI to update, or just create the secrets in gcloud (delete the existing ones first)
gcloud secrets delete burn_sftp_ssh_keys --project=dse-nps --quiet
gcloud secrets create burn_sftp_ssh_keys --data-file=ssh_keys.json --project=dse-nps --quiet

# Remove the keys from the local filesystem
rm user_key user_key.pub
rm admin_key admin_key.pub
rm ssh_keys.json
