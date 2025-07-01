#!/bin/bash

echo "Creating .env file..."
# Check if the .env file exists and clear it if it does
if [ -f public/env.js ]; then
  >.env
fi
# Read the .env-example file
while read line; do
  # Check if the line is not empty and not a comment
  if [[ ! -z "$line" && "$line" != \#* ]]; then
    # Get the variable name and value
    var_name=$(echo "$line" | cut -d= -f1)
    var_value=$(echo "$line" | cut -d= -f2-)

    echo "Processing $var_name and $var_value"
    # Check if the value contains a Kubernetes or AWS command
    if [[ "$var_value" == kubectl* || "$var_value" == aws* ]]; then
      # Evaluate the command and get the variable value
      var_value=$(eval "$var_value")
    fi

    # Write the variable to the .env file
    echo "$var_name=$var_value" >>.env
  fi
done <.env.example
