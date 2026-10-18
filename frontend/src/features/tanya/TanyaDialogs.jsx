import { useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { toast } from "../../hooks/use-toast";
import { createMyTemplate, createSchedule } from "./tanyaApi";
import { PERIOD_LABELS, WEEKDAYS } from "./tanyaFormat";

function Chips({ options, value, onChange, testPrefix }) {
  return (
    <div className="tanya-periods">
      {options.map(([v, label]) => (
        <button key={v} type="button" className={`tanya-chip ${value === v ? "active" : ""}`} onClick={() => onChange(v)} data-testid={`${testPrefix}-${v}`}>{label}</button>
      ))}
    </div>
  );
}

/** Jadwalkan template: harian/mingguan, jam WIB, dikirim sebagai notifikasi aplikasi. */
export function TanyaScheduleDialog({ target, periodPresets, onClose, onSaved }) {
  const tpl = target?.template;
  const [form, setForm] = useState({});
  useEffect(() => {
    if (tpl) setForm({ title: tpl.title, frequency: "daily", weekday: 0, time: "07:00", period: target.params?.period || "mtd" });
  }, [tpl, target]);
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const save = async () => {
    try {
      const params = { ...(target.params || {}), ...(target.hasPeriod ? { period: form.period } : {}) };
      await createSchedule({ template_id: tpl.id, title: form.title, frequency: form.frequency, weekday: form.weekday, time: form.time, params });
      toast({ title: "Jadwal tersimpan", description: "Laporan akan dikirim ke notifikasi Anda." });
      onSaved?.(); onClose();
    } catch (e) {
      toast({ title: "Jadwal gagal disimpan", description: e?.response?.data?.detail || "", variant: "destructive" });
    }
  };
  return (
    <Dialog open={!!tpl} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="tanya-schedule-dialog">
        <DialogHeader><DialogTitle>Jadwalkan laporan</DialogTitle></DialogHeader>
        <div className="tanya-form">
          <Label>Judul</Label>
          <Input value={form.title || ""} onChange={(e) => set("title")(e.target.value)} data-testid="tanya-schedule-title" />
          <Label>Frekuensi</Label>
          <Chips options={[["daily", "Harian"], ["weekly", "Mingguan"]]} value={form.frequency} onChange={set("frequency")} testPrefix="tanya-schedule-freq" />
          {form.frequency === "weekly" && (
            <Chips options={WEEKDAYS.map((d, i) => [i, d])} value={form.weekday} onChange={set("weekday")} testPrefix="tanya-schedule-weekday" />
          )}
          <Label>Jam (WIB)</Label>
          <Input type="time" value={form.time || ""} onChange={(e) => set("time")(e.target.value)} data-testid="tanya-schedule-time" />
          {target?.hasPeriod && (<>
            <Label>Periode laporan</Label>
            <Chips options={(periodPresets || []).map((p) => [p, PERIOD_LABELS[p] || p])} value={form.period} onChange={set("period")} testPrefix="tanya-schedule-period" />
          </>)}
          <p className="tanya-note">Dikirim sebagai notifikasi aplikasi dengan hak akses Anda sendiri.</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="tanya-schedule-cancel">Batal</Button>
          <Button onClick={save} disabled={!form.time} data-testid="tanya-schedule-save">Simpan jadwal</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Simpan pertanyaan chat sebagai template pribadi (mode llm). */
export function TanyaSaveTemplateDialog({ question, onClose, onSaved }) {
  const [title, setTitle] = useState("");
  useEffect(() => { setTitle((question || "").slice(0, 80)); }, [question]);
  const save = async () => {
    try {
      await createMyTemplate({ title, question });
      toast({ title: "Template pribadi tersimpan" });
      onSaved?.(); onClose();
    } catch (e) {
      toast({ title: "Template gagal disimpan", description: e?.response?.data?.detail || "", variant: "destructive" });
    }
  };
  return (
    <Dialog open={!!question} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="tanya-save-template-dialog">
        <DialogHeader><DialogTitle>Simpan sebagai template saya</DialogTitle></DialogHeader>
        <div className="tanya-form">
          <Label>Nama template</Label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} data-testid="tanya-save-template-title" />
          <p className="tanya-note">Pertanyaan: &ldquo;{question}&rdquo;</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="tanya-save-template-cancel">Batal</Button>
          <Button onClick={save} disabled={!title.trim()} data-testid="tanya-save-template-submit">Simpan</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
