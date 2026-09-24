"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import { KYCStatusResponse } from "@/types";
import styles from "./kyc.module.css";

const INDIAN_STATES_AND_UTS = [
  "Delhi NCR",
  "Maharashtra",
  "Uttar Pradesh",
  "Karnataka",
  "Tamil Nadu",
  "Gujarat",
  "West Bengal",
  "Punjab & Haryana",
  "Rajasthan",
  "Madhya Pradesh",
  "Telangana",
  "Kerala",
  "Bihar",
  "Odisha",
  "Assam",
  "Jharkhand",
  "Uttarakhand",
  "Himachal Pradesh",
  "Goa",
  "Jammu & Kashmir",
  "Chandigarh",
  "Other State / Union Territory",
];

const ID_TYPES = [
  { value: "AADHAAR", label: "Aadhaar Card (UIDAI)" },
  { value: "PAN", label: "Permanent Account Number (PAN)" },
  { value: "VOTER_ID", label: "Voter Identity Card (EPIC)" },
  { value: "PASSPORT", label: "Indian Passport" },
  { value: "DRIVING_LICENSE", label: "Driving License" },
];

const STATE_BAR_COUNCILS = [
  "Bar Council of Delhi",
  "Bar Council of Maharashtra & Goa",
  "Bar Council of Uttar Pradesh",
  "Bar Council of Punjab & Haryana",
  "Bar Council of Karnataka",
  "Bar Council of Tamil Nadu",
  "Bar Council of West Bengal",
  "Bar Council of Gujarat",
  "Bar Council of Rajasthan",
];

const PRACTICE_AREAS = [
  "Criminal Law & Bail",
  "Civil Litigation & Injunctions",
  "Constitutional & Writ Petitions",
  "Family & Matrimonial Disputes",
  "Corporate & Commercial Arbitration",
  "Real Estate & Property Law",
  "Cheque Bounce (NI Act Sec 138)",
  "Insolvency & Bankruptcy (IBC)",
];

const PILOT_COURTS = [
  "High Court of Delhi",
  "High Court of Bombay",
  "High Court of Allahabad",
  "Delhi District Courts",
  "Mumbai City Civil & Sessions Court",
  "National Company Law Tribunal (NCLT)",
  "Debt Recovery Tribunal (DRT)",
];

function KYCContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading: authLoading, checkSession } = useAuth();

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [kycData, setKycData] = useState<KYCStatusResponse | null>(null);
  const [fetching, setFetching] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Client Form State
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("Male");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("New Delhi");
  const [state, setState] = useState(INDIAN_STATES_AND_UTS[0]);
  const [pincode, setPincode] = useState("");
  const [idType, setIdType] = useState(ID_TYPES[0].value);
  const [idNumber, setIdNumber] = useState("");

  // Document Upload State
  const [uploadedDocKey, setUploadedDocKey] = useState<string | null>(null);
  const [uploadedDocName, setUploadedDocName] = useState<string | null>(null);
  const [uploadingDoc, setUploadingDoc] = useState(false);

  // Lawyer Specific Form State
  const [barCouncil, setBarCouncil] = useState(STATE_BAR_COUNCILS[0]);
  const [enrollmentNo, setEnrollmentNo] = useState("");
  const [selectedAreas, setSelectedAreas] = useState<string[]>([PRACTICE_AREAS[0], PRACTICE_AREAS[1]]);
  const [selectedCourts, setSelectedCourts] = useState<string[]>([PILOT_COURTS[0]]);
  const [consultationFee, setConsultationFee] = useState("1000");

  // Consent checkboxes
  const [truthConsent, setTruthConsent] = useState(true);
  const [dpdpConsent, setDpdpConsent] = useState(true);

  const fetchKycStatus = useCallback(async () => {
    try {
      setFetching(true);
      const res = await apiClient.get<KYCStatusResponse>("/api/v1/kyc/status");
      setKycData(res);

      if (res.full_name) setFullName(res.full_name);
      if (res.phone) setPhone(res.phone);
      if (res.date_of_birth) setDob(res.date_of_birth);
      if (res.gender) setGender(res.gender);
      if (res.address) setAddress(res.address);
      if (res.city) setCity(res.city);
      if (res.state) setState(res.state);
      if (res.pincode) setPincode(res.pincode);
      if (res.id_type) setIdType(res.id_type);
      if (res.id_number) setIdNumber(res.id_number);
      if (res.kyc_document_filename) setUploadedDocName(res.kyc_document_filename);

      if (res.enrollment_number) setEnrollmentNo(res.enrollment_number);
      if (res.state_bar_council) setBarCouncil(res.state_bar_council);

      // If already verified and no force edit
      if (res.is_kyc_completed && !searchParams.get("edit")) {
        setSuccess(true);
      }
    } catch (err) {
      console.warn("Could not fetch KYC status dossier:", err);
    } finally {
      setFetching(false);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login?redirect=/kyc");
      return;
    }
    if (user) {
      if (!fullName && user.full_name) setFullName(user.full_name);
      void fetchKycStatus();
    }
  }, [user, authLoading, router, fullName, fetchKycStatus]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setUploadingDoc(true);

    try {
      if (user?.role === "LAWYER") {
        // Upload advocate verification document
        const formData = new FormData();
        formData.append("file", file);
        formData.append("document_type", "BAR_COUNCIL_ENROLLMENT_CERT");

        const res = await apiClient.post<{
          id: string;
          original_filename: string;
        }>("/api/v1/verification/application/documents", formData);

        setUploadedDocKey(res.id);
        setUploadedDocName(res.original_filename);
      } else {
        // Upload client KYC proof
        const formData = new FormData();
        formData.append("file", file);

        const res = await apiClient.post<{
          storage_key: string;
          filename: string;
        }>("/api/v1/kyc/client/document", formData);

        setUploadedDocKey(res.storage_key);
        setUploadedDocName(res.filename);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Document upload failed.";
      setError(msg);
    } finally {
      setUploadingDoc(false);
    }
  };

  const validateStep1 = (): boolean => {
    if (!fullName.trim() || fullName.trim().length < 2) {
      setError("Please provide your full legal name as shown on official identity records.");
      return false;
    }
    const cleanPhone = phone.replace(/[\s\-\(\)\+]/g, "");
    if (cleanPhone.length < 10) {
      setError("Please provide a valid 10-digit Indian mobile number.");
      return false;
    }
    setError(null);
    return true;
  };

  const validateStep2 = (): boolean => {
    if (!address.trim() || address.trim().length < 3) {
      setError("Please enter your residential address.");
      return false;
    }
    if (!city.trim()) {
      setError("Please enter your city.");
      return false;
    }
    const cleanPin = pincode.trim();
    if (!/^\d{6}$/.test(cleanPin)) {
      setError("Please enter a valid 6-digit Indian postal PIN code.");
      return false;
    }
    setError(null);
    return true;
  };

  const validateStep3 = (): boolean => {
    if (user?.role === "LAWYER") {
      const cleanEnroll = enrollmentNo.trim().toUpperCase();
      if (!cleanEnroll || !cleanEnroll.includes("/")) {
        setError("Please enter your enrollment number in standard STATE/NUMBER/YEAR format (e.g., D/1234/2018).");
        return false;
      }
      if (!uploadedDocName && !uploadedDocKey) {
        setError("Statutory requirement: Please upload your official Bar Council Certificate or ID.");
        return false;
      }
    } else {
      if (!idNumber.trim() || idNumber.trim().length < 4) {
        setError("Please provide a valid Identity Document number.");
        return false;
      }
      if (!uploadedDocName && !uploadedDocKey) {
        setError("Please upload an official proof of identity document (Aadhaar / PAN / Voter ID / Passport).");
        return false;
      }
    }
    setError(null);
    return true;
  };

  const handleNextStep = () => {
    if (step === 1 && !validateStep1()) return;
    if (step === 2 && !validateStep2()) return;
    if (step === 3 && !validateStep3()) return;
    setStep((prev) => (prev < 4 ? ((prev + 1) as 1 | 2 | 3 | 4) : prev));
  };

  const handlePrevStep = () => {
    setError(null);
    setStep((prev) => (prev > 1 ? ((prev - 1) as 1 | 2 | 3 | 4) : prev));
  };

  const handleSubmitKYC = async () => {
    if (!truthConsent || !dpdpConsent) {
      setError("Statutory undertakings and DPDP Act consent are required to submit KYC.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      if (user?.role === "LAWYER") {
        // Submit lawyer verification application
        await apiClient.post("/api/v1/verification/application/submit", {
          enrollment_number: enrollmentNo.trim().toUpperCase(),
          state_bar_council: barCouncil,
          declared_practice_jurisdictions: selectedCourts,
        });

        // Also update lawyer profile practice areas and fees
        await apiClient.patch("/api/v1/profiles/lawyer", {
          full_name: fullName.trim(),
          phone: phone.trim(),
          practice_areas: selectedAreas,
          court_jurisdictions: selectedCourts,
          consultation_fee: parseInt(consultationFee, 10) || 1000,
        }).catch(() => null);
      } else {
        // Submit client KYC
        await apiClient.post("/api/v1/kyc/client/submit", {
          full_name: fullName.trim(),
          phone: phone.trim(),
          date_of_birth: dob || null,
          gender: gender || null,
          id_type: idType,
          id_number: idNumber.trim().toUpperCase(),
          address: address.trim(),
          city: city.trim(),
          state: state.trim(),
          pincode: pincode.trim(),
          kyc_document_storage_key: uploadedDocKey,
          kyc_document_filename: uploadedDocName,
          dpdp_consent: dpdpConsent,
        });
      }

      // Re-validate session to update AuthProvider's user.is_kyc_completed
      await checkSession();
      setSuccess(true);

      // Auto redirect after 2.5 seconds
      const redirectParam = searchParams.get("redirect");
      setTimeout(() => {
        if (redirectParam && redirectParam.startsWith("/")) {
          router.push(redirectParam);
        } else if (user?.role === "LAWYER") {
          router.push("/lawyer/dashboard");
        } else {
          router.push("/dashboard");
        }
      }, 2500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record and verify KYC profile.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleContinueToDashboard = () => {
    const redirectParam = searchParams.get("redirect");
    if (redirectParam && redirectParam.startsWith("/")) {
      router.push(redirectParam);
    } else if (user?.role === "LAWYER") {
      router.push("/lawyer/dashboard");
    } else {
      router.push("/dashboard");
    }
  };

  if (fetching || authLoading) {
    return (
      <div className={styles.pageWrapper}>
        <div style={{ textAlign: "center", color: "#94A3B8", fontSize: "15px" }}>
          Initializing statutory verification workspace...
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pageWrapper}>
      <div className={styles.kycCard}>
        {/* Header */}
        <div className={styles.cardHeader}>
          <div className={styles.topPillRow}>
            <span className={styles.badge}>
              <span>⚖️</span>
              <span>{user?.role === "LAWYER" ? "Advocate Credential Verification" : "Litigant Profile Completion"}</span>
            </span>
            <span className={styles.compliancePill}>
              <span>🛡️</span>
              <span>DPDP Act 2023 & BCI Verified</span>
            </span>
          </div>
          <h1 className={styles.title}>
            {success
              ? "KYC Verification Completed"
              : user?.role === "LAWYER"
              ? "Advocate Bar Verification & Practice Profile"
              : "Complete Your Profile & KYC Verification"}
          </h1>
          <p className={styles.subtitle}>
            {success
              ? "Your profile has been authenticated. You now have full access to consultations, legal documents, and matter rooms."
              : user?.role === "LAWYER"
              ? "Verify your State Bar Council roll status to receive consultations, file appearances, and link with litigating clients."
              : "Authenticating your identity unlocks verified case management, scheduled advocate consultations, and compliant court filings."}
          </p>
        </div>

        {/* Step Indicator (Only if not in success view) */}
        {!success && (
          <div className={styles.stepTracker}>
            <div
              className={`${styles.stepItem} ${step === 1 ? styles.stepItemActive : ""} ${step > 1 ? styles.stepItemCompleted : ""}`}
              onClick={() => setStep(1)}
            >
              <div className={styles.stepNumber}>{step > 1 ? "✓" : "1"}</div>
              <span className={styles.stepLabel}>Personal</span>
            </div>
            <div className={`${styles.stepConnector} ${step >= 2 ? styles.stepConnectorActive : ""}`} />

            <div
              className={`${styles.stepItem} ${step === 2 ? styles.stepItemActive : ""} ${step > 2 ? styles.stepItemCompleted : ""}`}
              onClick={() => {
                if (validateStep1()) setStep(2);
              }}
            >
              <div className={styles.stepNumber}>{step > 2 ? "✓" : "2"}</div>
              <span className={styles.stepLabel}>Address</span>
            </div>
            <div className={`${styles.stepConnector} ${step >= 3 ? styles.stepConnectorActive : ""}`} />

            <div
              className={`${styles.stepItem} ${step === 3 ? styles.stepItemActive : ""} ${step > 3 ? styles.stepItemCompleted : ""}`}
              onClick={() => {
                if (validateStep1() && validateStep2()) setStep(3);
              }}
            >
              <div className={styles.stepNumber}>{step > 3 ? "✓" : "3"}</div>
              <span className={styles.stepLabel}>Identity</span>
            </div>
            <div className={`${styles.stepConnector} ${step >= 4 ? styles.stepConnectorActive : ""}`} />

            <div
              className={`${styles.stepItem} ${step === 4 ? styles.stepItemActive : ""}`}
              onClick={() => {
                if (validateStep1() && validateStep2() && validateStep3()) setStep(4);
              }}
            >
              <div className={styles.stepNumber}>4</div>
              <span className={styles.stepLabel}>Consent</span>
            </div>
          </div>
        )}

        {/* Body Content */}
        <div className={styles.cardBody}>
          {error && (
            <div className={styles.errorBanner}>
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* SUCCESS SCREEN */}
          {success ? (
            <div className={styles.successContainer}>
              <div className={styles.successIconBadge}>🛡️</div>
              <h2 style={{ fontSize: "22px", fontWeight: 700, margin: "8px 0", color: "#34D399" }}>
                Identity Dossier Verified & Complete
              </h2>
              <p style={{ color: "#94A3B8", fontSize: "14px", margin: 0, maxWidth: "420px" }}>
                Your identity credentials have been cryptographically stamped and registered.
              </p>

              <div className={styles.verifiedCard}>
                <div className={styles.verifiedRow}>
                  <span className={styles.verifiedLabel}>Legal Name</span>
                  <span className={styles.verifiedValue}>{fullName || user?.full_name || "Verified Participant"}</span>
                </div>
                <div className={styles.verifiedRow}>
                  <span className={styles.verifiedLabel}>Role</span>
                  <span className={styles.verifiedValue}>{user?.role === "LAWYER" ? "Advocate" : "Litigant (Client)"}</span>
                </div>
                <div className={styles.verifiedRow}>
                  <span className={styles.verifiedLabel}>KYC Status</span>
                  <span className={styles.verifiedValue} style={{ color: "#34D399" }}>
                    ✓ {kycData?.kyc_status || "VERIFIED"}
                  </span>
                </div>
                {user?.role === "LAWYER" ? (
                  <div className={styles.verifiedRow}>
                    <span className={styles.verifiedLabel}>Bar Roll No.</span>
                    <span className={styles.verifiedValue}>{enrollmentNo || kycData?.enrollment_number || "Enrolled"}</span>
                  </div>
                ) : (
                  <div className={styles.verifiedRow}>
                    <span className={styles.verifiedLabel}>Identity Document</span>
                    <span className={styles.verifiedValue}>{idType} ({idNumber || "Verified"})</span>
                  </div>
                )}
                <div className={styles.verifiedRow}>
                  <span className={styles.verifiedLabel}>Location / State</span>
                  <span className={styles.verifiedValue}>{city}, {state}</span>
                </div>
              </div>

              <div style={{ marginTop: "16px" }}>
                <button
                  type="button"
                  onClick={handleContinueToDashboard}
                  className={styles.btnPrimary}
                  style={{ padding: "14px 36px", fontSize: "15px" }}
                >
                  Continue to Workspace →
                </button>
              </div>
            </div>
          ) : (
            <div>
              {/* STEP 1: Personal Details */}
              {step === 1 && (
                <div>
                  <div className={styles.sectionHeader}>
                    <h2 className={styles.sectionTitle}>Step 1: Personal & Contact Information</h2>
                    <p className={styles.sectionSubtitle}>
                      Provide your official personal details exactly as they appear on government identity records.
                    </p>
                  </div>

                  <div className={styles.formGrid}>
                    <div className={styles.inputGroup}>
                      <label className={styles.label}>
                        Full Legal Name <span className={styles.required}>*</span>
                      </label>
                      <input
                        type="text"
                        className={styles.input}
                        placeholder="e.g. Rohan Sharma"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        required
                      />
                      <span className={styles.helperText}>As stated on Aadhaar, PAN, or Bar Council Certificate</span>
                    </div>

                    <div className={styles.inputGroup}>
                      <label className={styles.label}>
                        Mobile Number <span className={styles.required}>*</span>
                      </label>
                      <input
                        type="tel"
                        className={styles.input}
                        placeholder="+91 98765 43210"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        required
                      />
                      <span className={styles.helperText}>Used for hearing notifications and consultation alerts</span>
                    </div>

                    <div className={styles.inputGroup}>
                      <label className={styles.label}>Date of Birth</label>
                      <input
                        type="date"
                        className={styles.input}
                        value={dob}
                        onChange={(e) => setDob(e.target.value)}
                      />
                    </div>

                    <div className={styles.inputGroup}>
                      <label className={styles.label}>Gender</label>
                      <select
                        className={styles.select}
                        value={gender}
                        onChange={(e) => setGender(e.target.value)}
                      >
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                        <option value="Other">Other / Non-Binary</option>
                        <option value="Prefer not to say">Prefer not to say</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {/* STEP 2: Address & Jurisdiction */}
              {step === 2 && (
                <div>
                  <div className={styles.sectionHeader}>
                    <h2 className={styles.sectionTitle}>Step 2: Address & Legal Jurisdiction</h2>
                    <p className={styles.sectionSubtitle}>
                      Accurate residential address is mandatory for court summons, notices, and jurisdictional matching.
                    </p>
                  </div>

                  <div className={styles.formGrid}>
                    <div className={`${styles.inputGroup} ${styles.fullWidth}`}>
                      <label className={styles.label}>
                        Street Address / Premise <span className={styles.required}>*</span>
                      </label>
                      <textarea
                        className={styles.textarea}
                        placeholder="Flat / House No., Building Name, Street / Locality"
                        value={address}
                        onChange={(e) => setAddress(e.target.value)}
                        required
                      />
                    </div>

                    <div className={styles.inputGroup}>
                      <label className={styles.label}>
                        City / District <span className={styles.required}>*</span>
                      </label>
                      <input
                        type="text"
                        className={styles.input}
                        placeholder="e.g. New Delhi"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        required
                      />
                    </div>

                    <div className={styles.inputGroup}>
                      <label className={styles.label}>
                        State / Union Territory <span className={styles.required}>*</span>
                      </label>
                      <select
                        className={styles.select}
                        value={state}
                        onChange={(e) => setState(e.target.value)}
                        required
                      >
                        {INDIAN_STATES_AND_UTS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className={styles.inputGroup}>
                      <label className={styles.label}>
                        PIN Code <span className={styles.required}>*</span>
                      </label>
                      <input
                        type="text"
                        maxLength={6}
                        className={styles.input}
                        placeholder="e.g. 110001"
                        value={pincode}
                        onChange={(e) => setPincode(e.target.value)}
                        required
                      />
                      <span className={styles.helperText}>6-digit Indian Postal Code</span>
                    </div>
                  </div>
                </div>
              )}

              {/* STEP 3: Identity Document Proof */}
              {step === 3 && (
                <div>
                  <div className={styles.sectionHeader}>
                    <h2 className={styles.sectionTitle}>
                      {user?.role === "LAWYER" ? "Step 3: Bar Council Enrollment & Certificate" : "Step 3: Identity Document Proof"}
                    </h2>
                    <p className={styles.sectionSubtitle}>
                      {user?.role === "LAWYER"
                        ? "Submit your official State Bar Council enrollment credentials and certificate."
                        : "Select an official Government identity document and provide a scanned copy (PDF or photo)."}
                    </p>
                  </div>

                  {user?.role === "LAWYER" ? (
                    <div className={styles.formGrid}>
                      <div className={styles.inputGroup}>
                        <label className={styles.label}>
                          State Bar Council <span className={styles.required}>*</span>
                        </label>
                        <select
                          className={styles.select}
                          value={barCouncil}
                          onChange={(e) => setBarCouncil(e.target.value)}
                          required
                        >
                          {STATE_BAR_COUNCILS.map((bc) => (
                            <option key={bc} value={bc}>
                              {bc}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className={styles.inputGroup}>
                        <label className={styles.label}>
                          Bar Enrollment Number <span className={styles.required}>*</span>
                        </label>
                        <input
                          type="text"
                          className={styles.input}
                          placeholder="e.g. D/1234/2018"
                          value={enrollmentNo}
                          onChange={(e) => setEnrollmentNo(e.target.value)}
                          required
                        />
                        <span className={styles.helperText}>STATE/NUMBER/YEAR format</span>
                      </div>

                      <div className={styles.inputGroup}>
                        <label className={styles.label}>Initial Consultation Fee (₹)</label>
                        <input
                          type="number"
                          min={500}
                          max={5000}
                          className={styles.input}
                          value={consultationFee}
                          onChange={(e) => setConsultationFee(e.target.value)}
                        />
                        <span className={styles.helperText}>Pilot cap: ₹500 - ₹2,500</span>
                      </div>

                      <div className={`${styles.inputGroup} ${styles.fullWidth}`}>
                        <label className={styles.label}>
                          Bar Certificate or ID Upload <span className={styles.required}>*</span>
                        </label>
                        <label className={styles.dropzone}>
                          <input
                            type="file"
                            accept=".pdf,image/png,image/jpeg,image/webp"
                            style={{ display: "none" }}
                            onChange={handleFileUpload}
                            disabled={uploadingDoc}
                          />
                          <div className={styles.dropzoneIcon}>📄</div>
                          <p className={styles.dropzoneTitle}>
                            {uploadingDoc ? "Encrypting and uploading certificate..." : "Click to upload Bar Council Enrollment Certificate"}
                          </p>
                          <p className={styles.dropzoneSubtitle}>Supported formats: PDF, PNG, JPG (Max 5MB)</p>
                        </label>

                        {uploadedDocName && (
                          <div className={styles.uploadedFilePill}>
                            <div className={styles.fileInfo}>
                              <span>✓</span>
                              <span>{uploadedDocName}</span>
                            </div>
                            <span style={{ fontSize: "11px", color: "#34D399" }}>Uploaded & Hashed</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className={styles.formGrid}>
                      <div className={styles.inputGroup}>
                        <label className={styles.label}>
                          Government ID Type <span className={styles.required}>*</span>
                        </label>
                        <select
                          className={styles.select}
                          value={idType}
                          onChange={(e) => setIdType(e.target.value)}
                          required
                        >
                          {ID_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className={styles.inputGroup}>
                        <label className={styles.label}>
                          Document ID Number <span className={styles.required}>*</span>
                        </label>
                        <input
                          type="text"
                          className={styles.input}
                          placeholder={idType === "PAN" ? "ABCDE1234F" : "XXXX-XXXX-XXXX"}
                          value={idNumber}
                          onChange={(e) => setIdNumber(e.target.value)}
                          required
                        />
                        <span className={styles.helperText}>Encrypted with AES-256 at rest</span>
                      </div>

                      <div className={`${styles.inputGroup} ${styles.fullWidth}`}>
                        <label className={styles.label}>
                          Upload ID Proof Document <span className={styles.required}>*</span>
                        </label>
                        <label className={styles.dropzone}>
                          <input
                            type="file"
                            accept=".pdf,image/png,image/jpeg,image/webp"
                            style={{ display: "none" }}
                            onChange={handleFileUpload}
                            disabled={uploadingDoc}
                          />
                          <div className={styles.dropzoneIcon}>📁</div>
                          <p className={styles.dropzoneTitle}>
                            {uploadingDoc ? "Processing document..." : "Click to select or drag & drop proof of identity"}
                          </p>
                          <p className={styles.dropzoneSubtitle}>
                            Upload front & back of Aadhaar, PAN card, or Passport (PDF, PNG, JPG up to 5MB)
                          </p>
                        </label>

                        {uploadedDocName && (
                          <div className={styles.uploadedFilePill}>
                            <div className={styles.fileInfo}>
                              <span>✓</span>
                              <span>{uploadedDocName}</span>
                            </div>
                            <span style={{ fontSize: "11px", color: "#34D399" }}>Attached securely</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* STEP 4: Consent & Submission */}
              {step === 4 && (
                <div>
                  <div className={styles.sectionHeader}>
                    <h2 className={styles.sectionTitle}>Step 4: Statutory Undertaking & Review</h2>
                    <p className={styles.sectionSubtitle}>
                      Review your profile details and confirm statutory legal consent before submitting your KYC.
                    </p>
                  </div>

                  <div className={styles.verifiedCard} style={{ maxWidth: "100%", marginBottom: "20px" }}>
                    <div className={styles.verifiedRow}>
                      <span className={styles.verifiedLabel}>Name</span>
                      <span className={styles.verifiedValue}>{fullName}</span>
                    </div>
                    <div className={styles.verifiedRow}>
                      <span className={styles.verifiedLabel}>Phone</span>
                      <span className={styles.verifiedValue}>{phone}</span>
                    </div>
                    <div className={styles.verifiedRow}>
                      <span className={styles.verifiedLabel}>Address</span>
                      <span className={styles.verifiedValue}>{address}, {city}, {state} - {pincode}</span>
                    </div>
                    {user?.role === "LAWYER" ? (
                      <div className={styles.verifiedRow}>
                        <span className={styles.verifiedLabel}>Bar Roll No.</span>
                        <span className={styles.verifiedValue}>{enrollmentNo} ({barCouncil})</span>
                      </div>
                    ) : (
                      <div className={styles.verifiedRow}>
                        <span className={styles.verifiedLabel}>ID Document</span>
                        <span className={styles.verifiedValue}>{idType} ({idNumber})</span>
                      </div>
                    )}
                    <div className={styles.verifiedRow}>
                      <span className={styles.verifiedLabel}>Uploaded Proof</span>
                      <span className={styles.verifiedValue} style={{ color: "#38BDF8" }}>
                        {uploadedDocName || "Document attached"}
                      </span>
                    </div>
                  </div>

                  <div className={styles.consentBox}>
                    <label className={styles.consentRow}>
                      <input
                        type="checkbox"
                        className={styles.checkbox}
                        checked={truthConsent}
                        onChange={(e) => setTruthConsent(e.target.checked)}
                      />
                      <span className={styles.consentText}>
                        <strong>Statutory Declaration:</strong> I solemnly affirm that all personal credentials, address details, and identity documents provided herein are authentic, accurate, and belong to me.
                      </span>
                    </label>

                    <label className={styles.consentRow}>
                      <input
                        type="checkbox"
                        className={styles.checkbox}
                        checked={dpdpConsent}
                        onChange={(e) => setDpdpConsent(e.target.checked)}
                      />
                      <span className={styles.consentText}>
                        <strong>DPDP Act 2023 Consent:</strong> I voluntarily consent to the collection, verification, and cryptographic storage of my KYC details for identity authentication in accordance with the Digital Personal Data Protection Act 2023.
                      </span>
                    </label>
                  </div>
                </div>
              )}

              {/* Navigation Button Row */}
              <div className={styles.buttonRow}>
                {step > 1 ? (
                  <button type="button" onClick={handlePrevStep} className={styles.btnSecondary} disabled={submitting}>
                    ← Back
                  </button>
                ) : (
                  <div />
                )}

                {step < 4 ? (
                  <button type="button" onClick={handleNextStep} className={styles.btnPrimary}>
                    Continue →
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleSubmitKYC}
                    className={styles.btnPrimary}
                    disabled={submitting || !truthConsent || !dpdpConsent}
                  >
                    {submitting ? "Verifying Credentials..." : "Submit & Complete KYC ✓"}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function KYCPage() {
  return (
    <Suspense fallback={<div className={styles.pageWrapper}>Loading KYC workspace...</div>}>
      <KYCContent />
    </Suspense>
  );
}
