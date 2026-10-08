# Push StudyMate to GitHub

1. Create a new **empty** repository on GitHub. Do not add a README or .gitignore there.
2. Open PowerShell in this folder and set your Git identity once:

```powershell
git config user.name "Your Name"
git config user.email "you@example.com"
```

3. Replace `YOUR-USERNAME` below with your GitHub username, then run:

```powershell
git remote add origin https://github.com/YOUR-USERNAME/StudyMate.git
git add .
git commit -m "Initial StudyMate project"
git branch -M main
git push -u origin main
```

The real API key is not included. `.env` files, dependency folders, caches, build output, and logs are excluded. Add your own key to `backend/.env` only on your computer after cloning.
