:: This is a reusable script for future updates.
:: It will add ALL changes and ask for a commit message.
@echo off

echo.
echo --- Staging all new and modified files...
git add .

echo.
set /p commitMessage="Enter your commit message: "

echo.
echo --- Committing with message: "%commitMessage%"
git commit -m "%commitMessage%"

echo.
echo --- Pushing changes to the remote repository...
git push origin main

echo.
echo =================================
echo  Update pushed successfully!
echo =================================
pause
