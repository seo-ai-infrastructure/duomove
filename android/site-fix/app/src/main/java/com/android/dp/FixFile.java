package com.android.dp;

import android.app.Application;
import android.os.SystemClock;
import android.util.Log;
import org.json.JSONObject;
import org.json.JSONTokener;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.lang.ref.WeakReference;
import java.util.*;
import net.stakeout.duomove.fixture.Fix;

/** File transport only. Nothing in this class creates or delivers Locations. */
final class FixFile {
    private final File file;
    private Fix current,lastAccepted;
    private String acceptedText;
    private long nextRead;
    private String state="";
    private final List<Binding> bindings=new ArrayList<>();
    private static final class Binding {
        final WeakReference<Object> object; final Fix snapshot;
        Binding(Object o,Fix f){ object=new WeakReference<>(o);snapshot=f; }
    }
    FixFile(Application app){ file=new File(app.getFilesDir(),"duomove/fix.json"); }
    private void status(String s){
        if (!state.equals(s)) { state=s;Log.i("site_fix","fixture_state="+s); }
    }
    private void refresh(long wall,long elapsed){
        if(elapsed<nextRead) return;
        nextRead=elapsed+500;
        try {
            if(Files.isSymbolicLink(file.toPath()) || !file.isFile() || file.length()>8192)
                throw new IOException("unavailable");
            byte[] bytes;
            try(InputStream in=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] b=new byte[1024];int n;
                while((n=in.read(b))!=-1){if(out.size()+n>8192)throw new IOException("too_large");out.write(b,0,n);}
                bytes=out.toByteArray();
            }
            String text=new String(bytes,StandardCharsets.UTF_8);
            JSONTokener tokens=new JSONTokener(text);
            Object value=tokens.nextValue();
            if(!(value instanceof JSONObject)||tokens.nextClean()!=0) throw new IOException("json");
            JSONObject json=(JSONObject)value;
            Map<String,Object> fields=new HashMap<>();
            Iterator<String> keys=json.keys();
            while(keys.hasNext()){String k=keys.next();fields.put(k,json.isNull(k)?null:json.get(k));}
            Fix candidate=Fix.parse(fields,wall,elapsed);
            if(candidate.newerThan(lastAccepted)){
                current=candidate;lastAccepted=candidate;acceptedText=text;
            } else if(text.equals(acceptedText) && lastAccepted.fresh(wall,elapsed)){
                current=lastAccepted; // Reading the same file never extends its expiry.
            } else throw new IOException("replay_or_changed_sequence");
            status("ACTIVE_TEST_FIXTURE");
        } catch(Exception e){current=null;status("PASSTHROUGH_MISSING_INVALID_OR_STALE");}
    }
    synchronized Fix forObject(Object object){
        long wall=System.currentTimeMillis(),elapsed=SystemClock.elapsedRealtime();
        refresh(wall,elapsed);
        if(current==null||!current.fresh(wall,elapsed)) return null;
        // Identity comparison avoids Location.hashCode() changing or getter recursion.
        Iterator<Binding> it=bindings.iterator();
        while(it.hasNext()){
            Binding b=it.next();Object o=b.object.get();
            if(o==null){it.remove();continue;}
            if(o==object) return b.snapshot!=null&&b.snapshot.fresh(wall,elapsed)?b.snapshot:null;
        }
        if(bindings.size()>=512){status("PASSTHROUGH_BINDING_LIMIT");return null;}
        bindings.add(new Binding(object,current));
        return current;
    }
}
