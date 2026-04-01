#!/bin/bash
# Initial repo setup script (already completed)
cd kiddom-sales-process-gpt
git init
git add .
git commit -m "chore: initial repo for kiddom sales process assistant"
git remote add origin git@github.com:neil2421/kiddom-sales-process-gpt.git
git branch -M main
git push -u origin main
