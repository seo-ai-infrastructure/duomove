package net.stakeout.duomove.checker;
import android.app.Activity;
import android.os.*;
import android.location.Location;
import android.widget.TextView;
import android.util.Log;
import java.io.File;
import java.util.Locale;

/** Owned test app: deliberately creates synthetic objects; requests no real fixes. */
public final class MainActivity extends Activity {
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView text;
    private final Runnable tick=new Runnable(){public void run(){showFixture();handler.postDelayed(this,1000);}};
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        new File(getFilesDir(),"duomove").mkdirs();
        text=new TextView(this);text.setTextSize(16);text.setPadding(24,32,24,24);setContentView(text);
    }
    @Override protected void onResume(){super.onResume();handler.post(tick);}
    @Override protected void onPause(){handler.removeCallbacks(tick);super.onPause();}
    private void showFixture(){
        Location l=new Location("duomove-test-object");
        l.setLatitude(0);l.setLongitude(0);l.setAccuracy(100);
        l.setTime(System.currentTimeMillis());l.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos());
        if(Build.VERSION.SDK_INT>=31)l.setMock(true);
        String s=String.format(Locale.US,
            "SYNTHETIC GETTER TEST — NOT GPS\n\nNew Location object each second.\nNo location listener or HTTPS endpoint.\n\nlat=%.7f lon=%.7f\naccuracy=%.2f\nhasAltitude=%s altitude=%.2f\nhasSpeed=%s speed=%.2f m/s\nhasBearing=%s bearing=%.2f\nhasVerticalAccuracy=%s vertical=%.2f\nprovider=%s\nmock=%s (unchanged by module)\n\nZero coordinates = original test object.\nCheck logcat site_fix for activation/errors.",
            l.getLatitude(),l.getLongitude(),l.getAccuracy(),l.hasAltitude(),l.getAltitude(),
            l.hasSpeed(),l.getSpeed(),l.hasBearing(),l.getBearing(),l.hasVerticalAccuracy(),
            l.getVerticalAccuracyMeters(),l.getProvider(),Build.VERSION.SDK_INT>=31?l.isMock():l.isFromMockProvider());
        text.setText(s);Log.i("duomove_checker",s);
    }
}
