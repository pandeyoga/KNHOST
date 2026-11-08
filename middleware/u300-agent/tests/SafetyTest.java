import id.kubusteknologi.kn.u300.core.Safety;
public class SafetyTest {
    static int checks;
    static void check(boolean value) { checks++; if(!value) throw new AssertionError("check "+checks); }
    public static void main(String[] args) {
        check("E20034120123456789ABCDEF".equals(Safety.canonicalEpc(" e20034120123456789abcdef ")));
        check(Safety.canonicalEpc("123") == null); check(Safety.canonicalEpc(null)==null);
        check(!Safety.durableAck("accepted",false)); check(Safety.durableAck("duplicate",true));
        check(!Safety.durableAck("quarantined",true)); check(!Safety.durableAck("retry",true));
        check(Safety.retryMillis(99,1000,60000)==60000);
        check(Safety.greenAllowed(true,true,true,true,true,true,false,true,true,"GREEN","manifest_full"));
        for(int bit=0;bit<9;bit++) {
            boolean[] b={true,true,true,true,true,true,false,true,true}; b[bit]=!b[bit];
            check(!Safety.greenAllowed(b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],b[8],"GREEN","manifest_full"));
        }
        check(!Safety.greenAllowed(true,true,true,true,true,true,false,true,true,"GREEN","per_epc_only"));
        check(!Safety.greenAllowed(true,true,true,true,true,true,false,true,true,"RED","manifest_full"));
        Safety.Direction d=new Safety.Direction(); check(d.edge("A",0,1000).equals("unknown"));
        check(d.edge("B",500,1000).equals("out")); check(d.edge("A",600,1000).equals("unknown"));
        d=new Safety.Direction(); d.edge("B",0,1000); check(d.edge("A",1001,1000).equals("unknown"));
        System.out.println("PASS: "+checks+" safety assertions");
    }
}
