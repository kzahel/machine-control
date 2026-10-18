plugins { id("com.android.application") }
android {
    namespace = "dev.machinecontrol.android.spike"
    compileSdk = 36
    defaultConfig {
        applicationId = "dev.machinecontrol.android.spike"
        minSdk = 30
        targetSdk = 36
        versionCode = 1
        versionName = "0.1-spike"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { buildConfig = true }
}
