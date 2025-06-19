plugins {
    kotlin("jvm") version "1.9.20"
    application
}

group = "org.example"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    // KotlinInside 라이브러리 의존성 추가
    implementation("be.zvz:KotlinInside:1.16.2")
    // 코루틴 의존성 추가 (KotlinInside가 내부적으로 사용)
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")

    // 컴파일 오류 해결을 위해 OkHttp 의존성 명시적으로 추가
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
}

application {
    mainClass.set("MainKt")
}

tasks.withType<Jar> {
    manifest {
        attributes["Main-Class"] = "MainKt"
    }
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
    from(sourceSets.main.get().output)
    dependsOn(configurations.runtimeClasspath)
    from({
        configurations.runtimeClasspath.get().filter { it.name.endsWith("jar") }.map { zipTree(it) }
    })
} 