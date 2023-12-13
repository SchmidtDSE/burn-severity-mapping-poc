#!/bin/sh

curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-457.0.0-linux-x86_64.tar.gz -o gcloud.tar.gz
tar -xzf gcloud.tar.gz 
./google-cloud-sdk/install.sh 
rm -rf gcloud.tar.gz google-cloud-sdk
./google-cloud-sdk/bin/gcloud init