package net.stakeout.duomove.fixture;
import java.util.*;
public final class FixTest {
    static int checks;
    static Map<String,Object> sample() {
        Map<String,Object> m = new HashMap<>();
        m.put("schema_version",1); m.put("generation",1); m.put("sequence",1);
        m.put("issued_at_ms",100_000L); m.put("ttl_ms",10_000);
        m.put("lat",28.0444); m.put("lon",-81.9498); m.put("accuracy",10.0);
        return m;
    }
    static void check(boolean b) { checks++; if (!b) throw new AssertionError("check "+checks); }
    static void bad(String k,Object v) {
        Map<String,Object> m=sample();m.put(k,v);
        try { Fix.parse(m,100_000,20_000); throw new AssertionError("accepted "+k+"="+v); }
        catch(IllegalArgumentException expected) { checks++; }
    }
    public static void main(String[] args) {
        Fix f=Fix.parse(sample(),100_000,20_000);
        check(f.alt==null && f.speed==null && f.bearing==null);
        check(f.fresh(109_999,29_999)); check(!f.fresh(110_000,30_000));
        check(!f.fresh(100_000,30_000)); check(!f.fresh(97_000,21_000));
        check(!f.fresh(100_000,19_999));
        bad("lat",91); bad("lon",181); bad("speed",-1); bad("bearing",360);
        bad("lat",Double.NaN);bad("accuracy",Double.POSITIVE_INFINITY);
        bad("speed","1.0"); bad("lat",true);bad("accuracy",-1);
        bad("ttl_ms",30_001);bad("ttl_ms",0);bad("sequence",1.5);bad("sequence",-1);
        bad("schema_version",2);bad("unknown",123);bad("alt",59.2);
        Map<String,Object> m=sample();m.put("alt",59.2);m.put("altitude_datum","WGS84_ELLIPSOID");
        m.put("speed",12.5);m.put("bearing",184.0);m.put("vertical_accuracy",2.0);
        Fix g=Fix.parse(m,100_000,20_000);
        check(g.alt==59.2 && g.speed==12.5 && g.bearing==184.0);
        check(!g.newerThan(f));m.put("sequence",2);g=Fix.parse(m,100_000,20_000);
        check(g.newerThan(f)); m.put("generation",2);m.put("sequence",0);
        check(Fix.parse(m,100_000,20_000).newerThan(g));
        try { Fix.parse(sample(),111_000,20_000); throw new AssertionError("expired accepted"); }
        catch(IllegalArgumentException expected) { checks++; }
        System.out.println("FixTest: "+checks+" checks passed");
    }
}
