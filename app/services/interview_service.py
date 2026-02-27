# app/services/interview_service.py
# HireNext.ai — Interview Scheduling Service (MongoDB) — UPDATED for Calendar → Meeting edit
#
# ✅ Existing features kept:
# - timezone-aware storage (UTC for created/updated; local tz for slot math)
# - overlap-based booked marking (duration changes still show booked)
# - prevent overlaps on the day
# - prevent scheduling SAME candidate twice in the same batch (across any date)
# - calendar events serializer for calander.js
#
# ✅ NEW (for meeting.html edit page):
# - update_interview(interview_id, patch)
# - cancel_interview(interview_id)
#
# ✅ FIXES:
# - meeting_link_default patch is applied to screening_batches
# - batch update works for ObjectId OR string id
#
# ✅ NEW FIX (Remaining-to-schedule / prevent extra slots):
# - save_confirmed_interviews() now blocks scheduling if:
#     - remaining_to_schedule == 0
#     - OR len(interviews) > remaining_to_schedule
# - (recommended) only allows scheduling candidate_ids that are in shortlisted_candidates

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from flask import current_app
from zoneinfo import ZoneInfo


# =========================
# Configurable defaults
# =========================
DEFAULT_TZ = "Asia/Colombo"

# Working windows
WORK_START = time(10, 0)     # 10:00
WORK_END_1 = time(12, 0)     # 12:00
WORK_START_2 = time(15, 0)   # 15:00
WORK_END_2 = time(16, 30)    # 16:30

# Break window shown in UI
BREAK_START = time(12, 0)    # 12:00
BREAK_END = time(15, 0)      # 15:00


@dataclass
class Slot:
    start: Optional[str] = None  # "HH:MM"
    end: Optional[str] = None    # "HH:MM"
    label: str = ""
    is_break: bool = False
    is_booked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "label": self.label,
            "is_break": self.is_break,
            "is_booked": self.is_booked,
        }


class InterviewService:
    """
    Uses Mongo collections:
      - screening_batches
      - interviews
    """

    COLLECTION = "interviews"

    # ---------------------------------------------------------
    # Mongo helper
    # ---------------------------------------------------------
    @staticmethod
    def _db():
        return current_app.mongo.db

    @staticmethod
    def _oid(val: str) -> Optional[ObjectId]:
        try:
            return ObjectId(str(val))
        except Exception:
            return None

    @staticmethod
    def _maybe_oid(val: Any) -> Any:
        """
        If val looks like an ObjectId string, convert it.
        Otherwise return original value.
        """
        if isinstance(val, ObjectId):
            return val
        if isinstance(val, str):
            oid = InterviewService._oid(val)
            return oid if oid else val
        return val

    # ---------------------------------------------------------
    # Date/time helpers
    # ---------------------------------------------------------
    @staticmethod
    def _tzinfo(tz: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz or DEFAULT_TZ)
        except Exception:
            return ZoneInfo(DEFAULT_TZ)

    @staticmethod
    def _parse_date(date_iso: str) -> date:
        return datetime.strptime(date_iso, "%Y-%m-%d").date()

    @staticmethod
    def _hm(dt_t: time) -> str:
        return f"{dt_t.hour:02d}:{dt_t.minute:02d}"

    @staticmethod
    def _fmt_ampm(t_hm: str) -> str:
        hh, mm = t_hm.split(":")
        h = int(hh)
        suffix = "AM" if h < 12 else "PM"
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{mm} {suffix}"

    @staticmethod
    def _local_dt(date_iso: str, hm: str, tz: str) -> datetime:
        """Create timezone-aware datetime in local tz from 'YYYY-MM-DD' and 'HH:MM'."""
        d = InterviewService._parse_date(date_iso)
        hh, mm = hm.split(":")
        tzinfo = InterviewService._tzinfo(tz)
        return datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=tzinfo)

    @staticmethod
    def _parse_iso_as_aware(iso_str: str, tz: str) -> datetime:
        """
        Parse ISO string into timezone-aware datetime.
        - If ISO includes offset -> returns aware datetime.
        - If ISO is naive -> interpret as local time in provided tz.
        """
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=InterviewService._tzinfo(tz))
        return dt

    @staticmethod
    def _overlaps(a: Tuple[datetime, datetime], b: Tuple[datetime, datetime]) -> bool:
        return a[0] < b[1] and b[0] < a[1]

    @staticmethod
    def _normalize_existing_interval(
        row: Dict[str, Any],
        tz: str,
        date_iso: str,
    ) -> Optional[Tuple[datetime, datetime]]:
        """
        Supports:
          - start_time/end_time stored as ISO string OR
          - start_label/end_label stored as "HH:MM"
        Always returns timezone-aware datetimes.
        """
        st_iso = row.get("start_time")
        en_iso = row.get("end_time")
        if isinstance(st_iso, str) and isinstance(en_iso, str) and st_iso and en_iso:
            try:
                st = InterviewService._parse_iso_as_aware(st_iso, tz)
                en = InterviewService._parse_iso_as_aware(en_iso, tz)
                return (st, en)
            except Exception:
                pass

        st_lab = row.get("start_label")
        en_lab = row.get("end_label")
        if isinstance(st_lab, str) and isinstance(en_lab, str) and st_lab and en_lab:
            try:
                st = InterviewService._local_dt(date_iso, st_lab, tz)
                en = InterviewService._local_dt(date_iso, en_lab, tz)
                return (st, en)
            except Exception:
                return None

        return None

    # ---------------------------------------------------------
    # Slot generation
    # ---------------------------------------------------------
    @staticmethod
    def generate_day_slots(duration_min: int = 10) -> List[Slot]:
        """
        Creates a full-day slot list:
          10:00–12:00 slots
          break 12:00–15:00
          15:00–16:30 slots
        """
        dur = max(5, int(duration_min))
        slots: List[Slot] = []

        def add_range(t_start: time, t_end: time):
            cur = datetime(2000, 1, 1, t_start.hour, t_start.minute)
            end = datetime(2000, 1, 1, t_end.hour, t_end.minute)
            step = timedelta(minutes=dur)

            while cur + step <= end:
                st = f"{cur.hour:02d}:{cur.minute:02d}"
                nxt = cur + step
                en = f"{nxt.hour:02d}:{nxt.minute:02d}"
                label = f"{InterviewService._fmt_ampm(st)} - {InterviewService._fmt_ampm(en)}"
                slots.append(Slot(start=st, end=en, label=label))
                cur = nxt

        add_range(WORK_START, WORK_END_1)

        break_label = (
            f"{InterviewService._fmt_ampm(InterviewService._hm(BREAK_START))} - "
            f"{InterviewService._fmt_ampm(InterviewService._hm(BREAK_END))}"
        )
        slots.append(Slot(start=None, end=None, label=break_label, is_break=True))

        add_range(WORK_START_2, WORK_END_2)
        return slots

    # ---------------------------------------------------------
    # Read interviews
    # ---------------------------------------------------------
    @staticmethod
    def get_interviews_for_day(batch_id: str, date_iso: str) -> List[Dict[str, Any]]:
        db = InterviewService._db()
        return list(
            db[InterviewService.COLLECTION]
            .find({"batch_id": str(batch_id), "date": date_iso})
            .sort("start_time", 1)
        )

    @staticmethod
    def get_interviews_for_batch(batch_id: str) -> List[Dict[str, Any]]:
        db = InterviewService._db()
        return list(
            db[InterviewService.COLLECTION]
            .find({"batch_id": str(batch_id)})
            .sort([("date", 1), ("start_time", 1)])
        )

    @staticmethod
    def get_scheduled_candidate_ids_for_batch(batch_id: str) -> List[str]:
        rows = InterviewService.get_interviews_for_batch(batch_id)
        seen = set()
        out: List[str] = []
        for r in rows:
            cid = str(r.get("candidate_id") or "").strip()
            if cid and cid not in seen:
                seen.add(cid)
                out.append(cid)
        return out

    @staticmethod
    def get_interview_by_id(interview_id: str) -> Optional[Dict[str, Any]]:
        db = InterviewService._db()
        oid = InterviewService._oid(interview_id)
        if not oid:
            return None
        return db[InterviewService.COLLECTION].find_one({"_id": oid})

    # ---------------------------------------------------------
    # Slots with status (available/booked)
    # ---------------------------------------------------------
    @staticmethod
    def build_slots_with_status(
        batch_id: str,
        date_iso: str,
        duration_min: int,
        tz: str,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            slots: [ {start,end,label,is_break,is_booked}, ...],
            booked: [ "HH:MM-HH:MM", ...],
            interviews: [ ... ]
          }

        Booked marking is OVERLAP-based (duration changes still show booked).
        """
        tz = tz or DEFAULT_TZ
        tzinfo = InterviewService._tzinfo(tz)

        base_slots = InterviewService.generate_day_slots(duration_min)
        interviews = InterviewService.get_interviews_for_day(batch_id, date_iso)

        existing_intervals: List[Tuple[datetime, datetime]] = []
        for r in interviews:
            itv = InterviewService._normalize_existing_interval(r, tz, date_iso)
            if itv:
                existing_intervals.append((itv[0].astimezone(tzinfo), itv[1].astimezone(tzinfo)))

        booked_labels: List[str] = []

        for s in base_slots:
            if s.is_break or not s.start or not s.end:
                continue

            slot_itv = (
                InterviewService._local_dt(date_iso, s.start, tz),
                InterviewService._local_dt(date_iso, s.end, tz),
            )

            is_booked = any(InterviewService._overlaps(slot_itv, ex) for ex in existing_intervals)
            if is_booked:
                s.is_booked = True
                booked_labels.append(f"{s.start}-{s.end}")

        ser_int: List[Dict[str, Any]] = []
        for it in interviews:
            x = dict(it)
            if "_id" in x:
                x["_id"] = str(x["_id"])
            ser_int.append(x)

        return {
            "slots": [s.to_dict() for s in base_slots],
            "booked": sorted(list(set(booked_labels))),
            "interviews": ser_int,
        }

    # ---------------------------------------------------------
    # Validation helpers
    # ---------------------------------------------------------
    @staticmethod
    def _intervals_from_items(
        date_iso: str,
        items: List[Dict[str, Any]],
        tz: str,
    ) -> Tuple[bool, List[Tuple[datetime, datetime]], Optional[str]]:
        tz = tz or DEFAULT_TZ
        out: List[Tuple[datetime, datetime]] = []

        for it in items:
            st_lab = it.get("start_label")
            en_lab = it.get("end_label")
            if st_lab and en_lab:
                try:
                    st = InterviewService._local_dt(date_iso, str(st_lab), tz)
                    en = InterviewService._local_dt(date_iso, str(en_lab), tz)
                    out.append((st, en))
                    continue
                except Exception:
                    return False, [], "Invalid start_label/end_label"

            st_iso = it.get("start_time")
            en_iso = it.get("end_time")
            if isinstance(st_iso, str) and isinstance(en_iso, str) and st_iso and en_iso:
                try:
                    st = InterviewService._parse_iso_as_aware(st_iso, tz)
                    en = InterviewService._parse_iso_as_aware(en_iso, tz)
                    out.append((st, en))
                    continue
                except Exception:
                    return False, [], "Invalid start_time/end_time format"

            return False, [], "Each interview must include start_label/end_label or start_time/end_time"

        return True, out, None

    @staticmethod
    def validate_no_overlap(
        batch_id: str,
        date_iso: str,
        new_items: List[Dict[str, Any]],
        tz: str,
    ) -> Tuple[bool, Optional[str]]:
        tz = tz or DEFAULT_TZ

        existing = InterviewService.get_interviews_for_day(batch_id, date_iso)
        existing_intervals: List[Tuple[datetime, datetime]] = []
        for r in existing:
            itv = InterviewService._normalize_existing_interval(r, tz, date_iso)
            if itv:
                existing_intervals.append(itv)

        ok, new_intervals, err = InterviewService._intervals_from_items(date_iso, new_items, tz)
        if not ok:
            return False, err

        for i in range(len(new_intervals)):
            for j in range(i + 1, len(new_intervals)):
                if InterviewService._overlaps(new_intervals[i], new_intervals[j]):
                    return False, "Selected slots overlap each other."

        for ni in new_intervals:
            for ei in existing_intervals:
                if InterviewService._overlaps(ni, ei):
                    return False, "One or more selected slots are already booked."

        return True, None

    @staticmethod
    def validate_candidates_not_already_scheduled(
        batch_id: str,
        new_items: List[Dict[str, Any]],
    ) -> Tuple[bool, Optional[str]]:
        """
        Prevent scheduling same candidate_id twice in the same batch (across any date).
        """
        new_ids = [str(it.get("candidate_id") or "").strip() for it in new_items]
        new_ids = [x for x in new_ids if x]

        if not new_ids:
            return True, None

        db = InterviewService._db()
        exists = db[InterviewService.COLLECTION].find_one(
            {"batch_id": str(batch_id), "candidate_id": {"$in": new_ids}},
            {"candidate_id": 1, "candidate_name": 1}
        )
        if exists:
            name = exists.get("candidate_name") or "Candidate"
            return False, f"{name} is already scheduled in this batch."

        return True, None

    # ---------------------------
    # NEW: shortlist guard
    # ---------------------------
    @staticmethod
    def _extract_shortlisted_candidate_ids(batch_doc: Dict[str, Any]) -> set[str]:
        """
        Returns candidate_id set from batch_doc.shortlisted_candidates.

        Supports common shapes:
          - {"candidate_id": "..."}
          - {"_id": "..."}   (if you stored candidate as _id)
        """
        out: set[str] = set()
        for c in (batch_doc.get("shortlisted_candidates") or []):
            if not isinstance(c, dict):
                continue
            cid = c.get("candidate_id")
            if cid is None:
                cid = c.get("_id")
            cid_s = str(cid or "").strip()
            if cid_s:
                out.add(cid_s)
        return out

    @staticmethod
    def _remaining_to_schedule(batch_doc: Dict[str, Any], batch_id: str) -> Tuple[int, int, int]:
        """
        Returns (shortlisted_total, already_scheduled, remaining)
        """
        db = InterviewService._db()
        shortlisted_total = len(batch_doc.get("shortlisted_candidates") or [])
        already_scheduled = int(db[InterviewService.COLLECTION].count_documents({"batch_id": str(batch_id)}) or 0)
        remaining = max(0, int(shortlisted_total) - int(already_scheduled))
        return int(shortlisted_total), int(already_scheduled), int(remaining)

    # ---------------------------------------------------------
    # Save interviews
    # ---------------------------------------------------------
    @staticmethod
    def save_confirmed_interviews(
        batch_doc: Dict[str, Any],
        date_iso: str,
        tz: str,
        duration_min: int,
        meeting_link: str,
        interviews: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Inserts interview docs into `interviews` collection.

        Server-side safety:
        - validates no overlap on the day
        - validates candidates aren't already scheduled in this batch
        - ✅ blocks extra scheduling when remaining_to_schedule == 0
        - ✅ blocks when user sends more interviews than remaining slots for candidates
        - ✅ (recommended) only allows candidate_ids that exist in shortlisted_candidates
        """
        db = InterviewService._db()
        tz = tz or DEFAULT_TZ

        batch_id = str(batch_doc.get("_id") or batch_doc.get("batch_id") or "")
        if not batch_id:
            return {"ok": False, "error": "Invalid batch document"}

        if not isinstance(interviews, list) or not interviews:
            return {"ok": False, "error": "No interviews provided"}

        # ✅ NEW: remaining-to-schedule guard
        shortlisted_total, already_scheduled, remaining = InterviewService._remaining_to_schedule(batch_doc, batch_id)
        if remaining <= 0:
            return {"ok": False, "error": "All shortlisted candidates are already scheduled."}
        if len(interviews) > remaining:
            return {
                "ok": False,
                "error": f"Only {remaining} shortlisted candidate(s) remaining to schedule."
            }

        # ✅ NEW: restrict scheduling to shortlisted candidates (recommended)
        shortlisted_ids = InterviewService._extract_shortlisted_candidate_ids(batch_doc)
        # If shortlist has candidate IDs, enforce them
        if shortlisted_ids:
            for it in interviews:
                cid = str((it or {}).get("candidate_id") or "").strip()
                if not cid:
                    return {"ok": False, "error": "candidate_id is required for scheduling."}
                if cid not in shortlisted_ids:
                    return {"ok": False, "error": "Candidate is not shortlisted for this batch."}

        normalized: List[Dict[str, Any]] = []
        tzinfo = InterviewService._tzinfo(tz)

        for it in interviews:
            item = dict(it or {})

            if item.get("candidate_id") is not None:
                item["candidate_id"] = str(item.get("candidate_id"))

            if not item.get("start_label") or not item.get("end_label"):
                st_iso = item.get("start_time")
                en_iso = item.get("end_time")
                if isinstance(st_iso, str) and isinstance(en_iso, str) and st_iso and en_iso:
                    try:
                        st = InterviewService._parse_iso_as_aware(st_iso, tz).astimezone(tzinfo)
                        en = InterviewService._parse_iso_as_aware(en_iso, tz).astimezone(tzinfo)
                        item["start_label"] = f"{st.hour:02d}:{st.minute:02d}"
                        item["end_label"] = f"{en.hour:02d}:{en.minute:02d}"
                    except Exception:
                        pass

            if item.get("start_label") and item.get("end_label"):
                st_local = InterviewService._local_dt(date_iso, str(item["start_label"]), tz)
                en_local = InterviewService._local_dt(date_iso, str(item["end_label"]), tz)
                item["start_time"] = st_local.isoformat()
                item["end_time"] = en_local.isoformat()

            if item.get("start_time"):
                try:
                    st = InterviewService._parse_iso_as_aware(str(item["start_time"]), tz).astimezone(tzinfo)
                    item["start_time"] = st.isoformat()
                except Exception:
                    return {"ok": False, "error": "Invalid start_time"}
            if item.get("end_time"):
                try:
                    en = InterviewService._parse_iso_as_aware(str(item["end_time"]), tz).astimezone(tzinfo)
                    item["end_time"] = en.isoformat()
                except Exception:
                    return {"ok": False, "error": "Invalid end_time"}

            normalized.append(item)

        ok, msg = InterviewService.validate_candidates_not_already_scheduled(batch_id, normalized)
        if not ok:
            return {"ok": False, "error": msg or "Candidate already scheduled."}

        ok, msg = InterviewService.validate_no_overlap(batch_id, date_iso, normalized, tz)
        if not ok:
            return {"ok": False, "error": msg or "Overlap detected"}

        now_utc = datetime.now(timezone.utc)

        docs: List[Dict[str, Any]] = []
        for it in normalized:
            docs.append({
                "batch_id": batch_id,
                "job_id": str(batch_doc.get("job_id") or ""),
                "job_title": str(batch_doc.get("job_title") or ""),

                "candidate_id": str(it.get("candidate_id") or ""),
                "candidate_name": str(it.get("candidate_name") or it.get("name") or ""),
                "candidate_email": str(it.get("candidate_email") or it.get("email") or ""),

                "title": str(it.get("title") or ""),
                "type": str(it.get("type") or "Interview"),

                "date": date_iso,
                "start_time": str(it.get("start_time") or ""),
                "end_time": str(it.get("end_time") or ""),
                "start_label": str(it.get("start_label") or ""),
                "end_label": str(it.get("end_label") or ""),
                "tz": tz,

                "duration_min": int(duration_min),
                "meeting_link": str(it.get("meeting_link") or meeting_link or ""),

                "status": "SCHEDULED",
                "invite_sent": False,

                "created_at": now_utc,
                "updated_at": now_utc,
            })

        try:
            db[InterviewService.COLLECTION].insert_many(docs)
        except Exception as e:
            return {"ok": False, "error": f"DB insert failed: {e}"}

        # ✅ FIX: update screening_batches even if _id is a string
        try:
            batch_pk = InterviewService._maybe_oid(batch_doc.get("_id"))
            count = db[InterviewService.COLLECTION].count_documents({"batch_id": batch_id})
            db["screening_batches"].update_one(
                {"_id": batch_pk},
                {"$set": {
                    "interviews_scheduled": int(count),
                    "last_scheduled_date": date_iso,
                    "meeting_link_default": meeting_link or batch_doc.get("meeting_link_default", ""),
                    "updated_at": now_utc,
                }}
            )
        except Exception:
            pass

        return {
            "ok": True,
            "inserted": len(docs),
            "shortlisted_total": shortlisted_total,
            "already_scheduled_before": already_scheduled,
            "remaining_before": remaining,
        }

    # ---------------------------------------------------------
    # Calendar events
    # ---------------------------------------------------------
    @staticmethod
    def get_calendar_events(
        start_date: str,
        end_date: str,
        batch_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns interviews between date range (inclusive) suitable for calander.js.
        """
        db = InterviewService._db()

        q: Dict[str, Any] = {"date": {"$gte": start_date, "$lte": end_date}}
        if batch_id:
            q["batch_id"] = str(batch_id)

        rows = list(db[InterviewService.COLLECTION].find(q).sort([("date", 1), ("start_time", 1)]))

        out: List[Dict[str, Any]] = []
        for r in rows:
            x = dict(r)
            _id = x.get("_id")
            x["id"] = str(_id) if _id is not None else ""
            x.pop("_id", None)

            x["time"] = str(x.get("start_label") or "")

            if not x.get("title"):
                cand = x.get("candidate_name") or "Candidate"
                job = x.get("job_title") or "Interview"
                st = x.get("start_label") or ""
                x["title"] = f"{job} • {cand}" + (f" ({st})" if st else "")

            if not x.get("type"):
                x["type"] = "Interview"

            out.append(x)

        return out

    # =========================================================
    # meeting.html support (update / cancel)
    # =========================================================

    @staticmethod
    def _derive_labels_and_iso(
        *,
        date_iso: str,
        tz: str,
        time_hm: Optional[str] = None,
        duration_min: Optional[int] = None,
        start_label: Optional[str] = None,
        end_label: Optional[str] = None,
        start_time_iso: Optional[str] = None,
        end_time_iso: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Normalize scheduling fields into:
          - start_label (HH:MM)
          - end_label   (HH:MM)
          - start_time  (ISO with offset)
          - end_time    (ISO with offset)
        """
        tz = tz or DEFAULT_TZ
        tzinfo = InterviewService._tzinfo(tz)

        # A) time + duration
        if time_hm and duration_min:
            try:
                st_local = InterviewService._local_dt(date_iso, time_hm, tz)
                en_local = st_local + timedelta(minutes=int(duration_min))
                return True, {
                    "start_label": f"{st_local.hour:02d}:{st_local.minute:02d}",
                    "end_label": f"{en_local.hour:02d}:{en_local.minute:02d}",
                    "start_time": st_local.astimezone(tzinfo).isoformat(),
                    "end_time": en_local.astimezone(tzinfo).isoformat(),
                }, None
            except Exception:
                return False, {}, "Invalid time/duration"

        # B) labels
        if start_label and end_label:
            try:
                st_local = InterviewService._local_dt(date_iso, str(start_label), tz)
                en_local = InterviewService._local_dt(date_iso, str(end_label), tz)
                if en_local <= st_local:
                    return False, {}, "end_label must be after start_label"
                return True, {
                    "start_label": f"{st_local.hour:02d}:{st_local.minute:02d}",
                    "end_label": f"{en_local.hour:02d}:{en_local.minute:02d}",
                    "start_time": st_local.astimezone(tzinfo).isoformat(),
                    "end_time": en_local.astimezone(tzinfo).isoformat(),
                }, None
            except Exception:
                return False, {}, "Invalid start_label/end_label"

        # C) ISO times
        if start_time_iso and end_time_iso:
            try:
                st = InterviewService._parse_iso_as_aware(str(start_time_iso), tz).astimezone(tzinfo)
                en = InterviewService._parse_iso_as_aware(str(end_time_iso), tz).astimezone(tzinfo)
                if en <= st:
                    return False, {}, "end_time must be after start_time"
                return True, {
                    "start_label": f"{st.hour:02d}:{st.minute:02d}",
                    "end_label": f"{en.hour:02d}:{en.minute:02d}",
                    "start_time": st.isoformat(),
                    "end_time": en.isoformat(),
                }, None
            except Exception:
                return False, {}, "Invalid start_time/end_time"

        return True, {}, None

    @staticmethod
    def _validate_no_overlap_excluding_self(
        *,
        batch_id: str,
        date_iso: str,
        tz: str,
        self_oid: ObjectId,
        new_interval: Tuple[datetime, datetime],
    ) -> Tuple[bool, Optional[str]]:
        db = InterviewService._db()
        tz = tz or DEFAULT_TZ

        rows = list(
            db[InterviewService.COLLECTION]
            .find({"batch_id": str(batch_id), "date": date_iso, "_id": {"$ne": self_oid}})
        )

        for r in rows:
            itv = InterviewService._normalize_existing_interval(r, tz, date_iso)
            if not itv:
                continue
            if InterviewService._overlaps(new_interval, itv):
                return False, "Selected time overlaps an existing booked interview."

        return True, None

    @staticmethod
    def _validate_candidate_not_duplicate_excluding_self(
        *,
        batch_id: str,
        candidate_id: str,
        self_oid: ObjectId,
    ) -> Tuple[bool, Optional[str]]:
        candidate_id = str(candidate_id or "").strip()
        if not candidate_id:
            return True, None

        db = InterviewService._db()
        exists = db[InterviewService.COLLECTION].find_one(
            {"batch_id": str(batch_id), "candidate_id": candidate_id, "_id": {"$ne": self_oid}},
            {"candidate_name": 1}
        )
        if exists:
            nm = exists.get("candidate_name") or "Candidate"
            return False, f"{nm} is already scheduled in this batch."
        return True, None

    @staticmethod
    def update_interview(interview_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        db = InterviewService._db()
        oid = InterviewService._oid(interview_id)
        if not oid:
            return {"ok": False, "error": "Invalid interview_id"}

        current = db[InterviewService.COLLECTION].find_one({"_id": oid})
        if not current:
            return {"ok": False, "error": "Interview not found"}

        batch_id = str(current.get("batch_id") or "")
        if not batch_id:
            return {"ok": False, "error": "Interview missing batch_id"}

        tz = str(patch.get("tz") or current.get("tz") or DEFAULT_TZ)
        date_iso = str(patch.get("date") or current.get("date") or "").strip()
        if not date_iso:
            return {"ok": False, "error": "date is required"}

        cand_id = str(patch.get("candidate_id") or current.get("candidate_id") or "").strip()
        ok, msg = InterviewService._validate_candidate_not_duplicate_excluding_self(
            batch_id=batch_id,
            candidate_id=cand_id,
            self_oid=oid
        )
        if not ok:
            return {"ok": False, "error": msg or "Candidate already scheduled."}

        time_hm = patch.get("time")
        duration_min = patch.get("duration") or patch.get("duration_min") or current.get("duration_min")

        start_label = patch.get("start_label")
        end_label = patch.get("end_label")
        start_time_iso = patch.get("start_time")
        end_time_iso = patch.get("end_time")

        must_recalc = any([
            patch.get("date") is not None,
            patch.get("time") is not None,
            patch.get("duration") is not None,
            patch.get("duration_min") is not None,
            patch.get("start_label") is not None,
            patch.get("end_label") is not None,
            patch.get("start_time") is not None,
            patch.get("end_time") is not None,
            patch.get("tz") is not None,
        ])

        derived: Dict[str, Any] = {}
        if must_recalc:
            if time_hm is None and start_label is None and start_time_iso is None:
                time_hm = str(current.get("start_label") or "")
                if not time_hm:
                    st_iso_cur = str(current.get("start_time") or "")
                    if st_iso_cur:
                        try:
                            st_dt = InterviewService._parse_iso_as_aware(st_iso_cur, tz)
                            time_hm = f"{st_dt.hour:02d}:{st_dt.minute:02d}"
                        except Exception:
                            time_hm = None

            ok, derived, err = InterviewService._derive_labels_and_iso(
                date_iso=date_iso,
                tz=tz,
                time_hm=str(time_hm) if time_hm else None,
                duration_min=int(duration_min) if duration_min else None,
                start_label=str(start_label) if start_label else None,
                end_label=str(end_label) if end_label else None,
                start_time_iso=str(start_time_iso) if start_time_iso else None,
                end_time_iso=str(end_time_iso) if end_time_iso else None,
            )
            if not ok:
                return {"ok": False, "error": err or "Invalid scheduling fields"}

            if derived.get("start_time") and derived.get("end_time"):
                try:
                    st = InterviewService._parse_iso_as_aware(str(derived["start_time"]), tz)
                    en = InterviewService._parse_iso_as_aware(str(derived["end_time"]), tz)
                    ok2, msg2 = InterviewService._validate_no_overlap_excluding_self(
                        batch_id=batch_id,
                        date_iso=date_iso,
                        tz=tz,
                        self_oid=oid,
                        new_interval=(st, en),
                    )
                    if not ok2:
                        return {"ok": False, "error": msg2 or "Time overlaps existing interview"}
                except Exception:
                    return {"ok": False, "error": "Invalid derived start/end time"}

        update_doc: Dict[str, Any] = {}

        for k in [
            "title", "type", "notes", "meeting_link", "status", "interviewer",
            "candidate_name", "candidate_email", "candidate_id", "job_title", "job_id"
        ]:
            if k in patch and patch[k] is not None:
                update_doc[k] = patch[k]

        if "tz" in patch and patch["tz"] is not None:
            update_doc["tz"] = tz
        if "date" in patch and patch["date"] is not None:
            update_doc["date"] = date_iso

        if "duration" in patch and patch["duration"] is not None:
            try:
                update_doc["duration_min"] = int(patch["duration"])
            except Exception:
                return {"ok": False, "error": "Invalid duration"}
        elif "duration_min" in patch and patch["duration_min"] is not None:
            try:
                update_doc["duration_min"] = int(patch["duration_min"])
            except Exception:
                return {"ok": False, "error": "Invalid duration_min"}

        if derived:
            update_doc.update(derived)

        update_doc["updated_at"] = datetime.now(timezone.utc)

        # Apply meeting_link_default to screening_batches
        if "meeting_link_default" in patch and patch["meeting_link_default"] is not None:
            try:
                db["screening_batches"].update_one(
                    {"_id": InterviewService._oid(batch_id) or batch_id},
                    {"$set": {
                        "meeting_link_default": str(patch["meeting_link_default"]),
                        "updated_at": datetime.now(timezone.utc),
                    }}
                )
            except Exception:
                pass

        try:
            db[InterviewService.COLLECTION].update_one({"_id": oid}, {"$set": update_doc})
        except Exception as e:
            return {"ok": False, "error": f"DB update failed: {e}"}

        updated = db[InterviewService.COLLECTION].find_one({"_id": oid})
        return {"ok": True, "interview": dict(updated) if updated else None}

    @staticmethod
    def cancel_interview(interview_id: str) -> Dict[str, Any]:
        db = InterviewService._db()
        oid = InterviewService._oid(interview_id)
        if not oid:
            return {"ok": False, "error": "Invalid interview_id"}

        row = db[InterviewService.COLLECTION].find_one({"_id": oid})
        if not row:
            return {"ok": False, "error": "Interview not found"}

        try:
            db[InterviewService.COLLECTION].update_one(
                {"_id": oid},
                {"$set": {
                    "status": "CANCELLED",
                    "updated_at": datetime.now(timezone.utc),
                    "cancelled_at": datetime.now(timezone.utc),
                }}
            )
        except Exception as e:
            return {"ok": False, "error": f"DB update failed: {e}"}

        updated = db[InterviewService.COLLECTION].find_one({"_id": oid})
        return {"ok": True, "interview": dict(updated) if updated else None}