# Build the APK with GitHub Actions

1. Create a new GitHub repository.
2. Upload the contents of this folder to the repository.
3. Commit/push to the `main` branch.
4. Open **Actions** in GitHub.
5. Select **Build APK**.
6. If it did not start automatically, choose **Run workflow**.
7. Open the completed workflow run.
8. Under **Artifacts**, download `StalkerIPTVPlayer-debug`.
9. Extract the downloaded artifact and install `app-debug.apk` on Android.

The workflow installs JDK 17, Android SDK platform 35/build tools 35.0.0, Gradle 8.10, builds the debug APK, and uploads the APK as a GitHub Actions artifact.

The application uses a manually entered MAC address. The automatic MAC-generation/brute-force feature from the original Python program is not included.
