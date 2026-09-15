package net.stakeout.duomove.fixture;

import java.util.*;

/** Immutable, explicitly synthetic getter fixture. Not an Android Location. */
public final class Fix {
    private static final Set<String> KEYS = new HashSet<>(Arrays.asList(
        "schema_version","generation","sequence","issued_at_ms","ttl_ms",
        "lat","lon","accuracy","alt","altitude_datum","speed","bearing","vertical_accuracy"));
    public final long generation,sequence,issuedAt,ttlMs,loadedElapsed,deadlineElapsed;
    public final double lat,lon,accuracy;
    public final Double alt,speed,bearing,verticalAccuracy;
    private Fix(Map<String,Object> m,long wall,long elapsed) {
        if (!KEYS.containsAll(m.keySet())) throw new IllegalArgumentException("unknown_field");
        if (integer(m,"schema_version",1,1)!=1) throw new IllegalArgumentException("schema");
        generation=integer(m,"generation",0,9_000_000_000_000_000L);
        sequence=integer(m,"sequence",0,9_000_000_000_000_000L);
        issuedAt=integer(m,"issued_at_ms",1,9_000_000_000_000_000L);
        ttlMs=integer(m,"ttl_ms",100,30_000);
        lat=number(m,"lat",-90,90);lon=number(m,"lon",-180,180);
        accuracy=number(m,"accuracy",0,100_000);
        alt=optional(m,"alt",-12_000,100_000);
        speed=optional(m,"speed",0,400);
        bearing=optional(m,"bearing",0,359.999999999);
        verticalAccuracy=optional(m,"vertical_accuracy",0,100_000);
        if (alt!=null && !"WGS84_ELLIPSOID".equals(m.get("altitude_datum")))
            throw new IllegalArgumentException("altitude_datum_required");
        if (alt==null && (m.get("altitude_datum")!=null || verticalAccuracy!=null))
            throw new IllegalArgumentException("altitude_required");
        long age=wall-issuedAt;
        if (age < -2000 || age>=ttlMs || elapsed<0) throw new IllegalArgumentException("stale_or_future");
        loadedElapsed=elapsed;
        deadlineElapsed=elapsed+ttlMs-Math.max(0,age);
    }
    public static Fix parse(Map<String,Object> m,long wall,long elapsed) { return new Fix(m,wall,elapsed); }
    public boolean fresh(long wall,long elapsed) {
        return elapsed>=loadedElapsed && elapsed<deadlineElapsed && wall>=issuedAt-2000 && wall-issuedAt<ttlMs;
    }
    public boolean newerThan(Fix other) {
        return other==null || generation>other.generation || (generation==other.generation && sequence>other.sequence);
    }
    private static double number(Map<String,Object> m,String key,double min,double max) {
        Object o=m.get(key);
        if (!(o instanceof Number)) throw new IllegalArgumentException("numeric_field_required");
        double n=((Number)o).doubleValue();
        if (!Double.isFinite(n)||n<min||n>max) throw new IllegalArgumentException("numeric_range");
        return n;
    }
    private static long integer(Map<String,Object> m,String key,long min,long max) {
        double n=number(m,key,min,max);
        if (n!=Math.rint(n)) throw new IllegalArgumentException("integer_required");
        return (long)n;
    }
    private static Double optional(Map<String,Object> m,String k,double min,double max) {
        return m.get(k)==null ? null : number(m,k,min,max);
    }
}
