package com.android.dp;

import android.app.Application;
import android.location.Location;
import android.os.Build;
import android.util.Log;
import com.android.dpbridge.LSPHelpers;
import com.android.dpbridge.LSP_MethodH;
import com.android.dpbridge.utils.DPLog;
import java.util.*;
import net.stakeout.duomove.fixture.Fix;

/** Dplus requires this exact class and init(Application) entrypoint. */
public final class Entry {
    private static final String TARGET="net.stakeout.duomove.checker";
    private static boolean installed;
    private interface Value { Object from(Fix fix); }
    public synchronized void init(Application app){
        if(!TARGET.equals(app.getPackageName()) || installed) return;
        FixFile file=new FixFile(app);
        List<LSP_MethodH.Unhook> hooks=new ArrayList<>();
        try{
            hook(hooks,file,"getLatitude",f->f.lat);
            hook(hooks,file,"getLongitude",f->f.lon);
            hook(hooks,file,"getAccuracy",f->(float)f.accuracy);
            hook(hooks,file,"hasAccuracy",f->true);
            hook(hooks,file,"getAltitude",f->f.alt==null?0.0:f.alt);
            hook(hooks,file,"hasAltitude",f->f.alt!=null);
            hook(hooks,file,"getSpeed",f->f.speed==null?0.0f:f.speed.floatValue());
            hook(hooks,file,"hasSpeed",f->f.speed!=null);
            hook(hooks,file,"getBearing",f->f.bearing==null?0.0f:f.bearing.floatValue());
            hook(hooks,file,"hasBearing",f->f.bearing!=null);
            hook(hooks,file,"getVerticalAccuracyMeters",f->f.verticalAccuracy==null?0.0f:f.verticalAccuracy.floatValue());
            hook(hooks,file,"hasVerticalAccuracy",f->f.verticalAccuracy!=null);
            hook(hooks,file,"hasSpeedAccuracy",f->false);
            hook(hooks,file,"getSpeedAccuracyMetersPerSecond",f->0.0f);
            hook(hooks,file,"hasBearingAccuracy",f->false);
            hook(hooks,file,"getBearingAccuracyDegrees",f->0.0f);
            if(Build.VERSION.SDK_INT>=34){
                hook(hooks,file,"hasMslAltitude",f->false);
                hook(hooks,file,"getMslAltitudeMeters",f->0.0);
                hook(hooks,file,"hasMslAltitudeAccuracy",f->false);
                hook(hooks,file,"getMslAltitudeAccuracyMeters",f->0.0f);
            }
            installed=true;
            DPLog.i("site_fix","enter init; checker-only getter fixture ready");
        }catch(Throwable failure){
            for(LSP_MethodH.Unhook h:hooks){try{h.unhook();}catch(Throwable ignored){}}
            Log.e("site_fix","hook_setup_failed; restart checker after unloading module");
        }
    }
    private void hook(List<LSP_MethodH.Unhook> hooks,FixFile file,String name,Value value){
        hooks.add(LSPHelpers.findAndHookMethod(Location.class,name,new LSP_MethodH(){
            @Override protected void afterHookedMethod(MethodHookParam param){
                if(param.hasThrowable())return;
                Fix fix=file.forObject(param.thisObject);
                if(fix!=null)param.setResult(value.from(fix));
            }
        }));
    }
}
