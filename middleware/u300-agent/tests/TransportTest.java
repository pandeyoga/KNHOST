package id.kubusteknologi.kn.u300;
import com.sun.net.httpserver.*;
import javax.net.ssl.*;
import java.net.*;
import java.security.*;
import java.nio.file.*;
import java.util.concurrent.atomic.*;
import org.json.*;
/** TLS integration against a loopback server. Trust override exists only inside this host test JVM. */
public final class TransportTest {
    static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("TLS check "+checks);}
    public static void main(String[] args)throws Exception{
        KeyStore keys=KeyStore.getInstance("PKCS12");try(java.io.InputStream in=Files.newInputStream(Paths.get(args[0]))){keys.load(in,"test-local-only".toCharArray());}
        KeyManagerFactory km=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());km.init(keys,"test-local-only".toCharArray());
        TrustManagerFactory tm=TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());tm.init(keys);
        SSLContext tls=SSLContext.getInstance("TLS");tls.init(km.getKeyManagers(),tm.getTrustManagers(),new SecureRandom());
        SSLSocketFactory original=HttpsURLConnection.getDefaultSSLSocketFactory();HttpsURLConnection.setDefaultSSLSocketFactory(tls.getSocketFactory());
        HttpsServer server=HttpsServer.create(new InetSocketAddress("127.0.0.1",0),0);server.setHttpsConfigurator(new HttpsConfigurator(tls));
        AtomicInteger mode=new AtomicInteger(200),trap=new AtomicInteger();AtomicReference<String> header=new AtomicReference<>(),key=new AtomicReference<>(),body=new AtomicReference<>();
        server.createContext("/api/rfid/v2/test",exchange->{
            header.set(exchange.getRequestHeaders().getFirst("X-Device-Key"));key.set(exchange.getRequestHeaders().getFirst("Idempotency-Key"));body.set(new String(exchange.getRequestBody().readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
            int status=mode.get();byte[] response=(status==299?new String(new char[2100000]).replace('\0','x'):"{\"ok\":true}").getBytes(java.nio.charset.StandardCharsets.UTF_8);
            if(status==302)exchange.getResponseHeaders().add("Location","/trap");if(status==429)exchange.getResponseHeaders().add("Retry-After","2");
            exchange.sendResponseHeaders(status==299?200:status,response.length);try{exchange.getResponseBody().write(response);}catch(java.io.IOException clientClosed){}finally{exchange.close();}
        });
        server.createContext("/trap",exchange->{trap.incrementAndGet();exchange.sendResponseHeaders(200,-1);exchange.close();});server.start();
        try{
            Api api=new Api(new Api.Settings(){public boolean simulation(){return false;}public String url(){return "https://127.0.0.1:"+server.getAddress().getPort();}public String token(){return "TEST_ONLY_DEVICE_KEY";}});
            check(api.call("POST","/test",Json.obj("payload","uji"),"stable-key").getBoolean("ok"));
            check("TEST_ONLY_DEVICE_KEY".equals(header.get()));check("stable-key".equals(key.get()));check(Json.parse(body.get()).getString("payload").equals("uji"));
            for(int code:new int[]{302,400,401,403,409,413,429,500}){
                mode.set(code);boolean rejected=false;try{api.call("POST","/test",Json.obj(),"same-key");}catch(Api.Failure e){rejected=e.status==code;if(code==429)check(e.retry==2000);}check(rejected);
            }
            check(trap.get()==0);
            mode.set(299);boolean oversized=false;try{api.call("GET","/test",null,null);}catch(java.io.IOException expected){oversized=true;}check(oversized);
            System.out.println("PASS: "+checks+" real HTTPS loopback assertions");
        }finally{server.stop(0);HttpsURLConnection.setDefaultSSLSocketFactory(original);}
    }
}
