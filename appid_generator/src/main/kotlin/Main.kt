import be.zvz.kotlininside.KotlinInside
import be.zvz.kotlininside.http.DefaultHttpClient
import be.zvz.kotlininside.session.user.Anonymous
import kotlinx.coroutines.runBlocking

fun main() {
    // KotlinInside 인스턴스 초기화 (유동닉으로 초기화, 실제 닉/비번은 필요 없음)
    KotlinInside.createInstance(
        Anonymous("ㅇㅇ", "1234"),
        DefaultHttpClient()
    )

    // 비동기 컨텍스트에서 app_id 요청
    runBlocking {
        try {
            val appId = KotlinInside.getInstance().auth.getAppId()
            print(appId) // 결과를 표준 출력으로 반환
        } catch (e: Exception) {
            System.err.println("Error getting app_id: ${e.message}")
        }
    }
} 