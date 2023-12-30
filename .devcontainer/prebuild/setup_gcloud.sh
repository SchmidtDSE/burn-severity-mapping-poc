#!/bin/bash

curl -o "gcloud.tar.gz" "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-457.0.0-linux-x86_64.tar.gz"
tar -xzf gcloud.tar.gz 
mv google-cloud-sdk /usr/local
/usr/local/google-cloud-sdk/install.sh --quiet
rm -rf gcloud.tar.gz
export PATH=$PATH:/usr/local/google-cloud-sdk/bin
