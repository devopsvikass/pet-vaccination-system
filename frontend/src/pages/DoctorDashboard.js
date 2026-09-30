import React, { useEffect, useRef, useState } from "react";
import API from "../api";
import { Link } from "react-router-dom";
import { countries, parseSelectedPhone, phoneLengthError } from "../utils/phone";
import "./DoctorDashboard.css";

function DoctorDashboard() {
  const [pets, setPets] = useState([]);
  const [phoneSearch, setPhoneSearch] = useState("");
  const [ownerCountry, setOwnerCountry] = useState("IN");
  const userId = localStorage.getItem("user_id");
  const [doctorStatus, setDoctorStatus] = useState("");
  const [doctorProfile, setDoctorProfile] = useState({ username: "", bio: "", profile_photo_url: "", email: "", phone: "" });
  const [profileForm, setProfileForm] = useState({ username: "", bio: "", email: "", phone: "" });
  const [profilePhoto, setProfilePhoto] = useState(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");
  const [profileError, setProfileError] = useState("");
  const [showProfileEdit, setShowProfileEdit] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [createMessage, setCreateMessage] = useState("");
  const [createError, setCreateError] = useState("");
  const [creating, setCreating] = useState(false);
  const [createdOwners, setCreatedOwners] = useState([]);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    owner_username: "",
    owner_email: "",
    owner_phone: "",
    owner_password: "",
    pet_name: "",
    pet_breed: "",
    pet_age: "",
    pet_vaccination_date: "",
  });
  const onboardingFormRef = useRef(null);
  const ownerUsernameInputRef = useRef(null);

  const statusLabel = doctorStatus
    ? `${doctorStatus.charAt(0).toUpperCase()}${doctorStatus.slice(1)}`
    : "Loading...";
    
  const statusBadgeClass =
    doctorStatus === "approved"
      ? "badge-approved"
      : doctorStatus === "pending"
        ? "badge-pending"
        : "badge-rejected";

  const loadPets = async (phone = "") => {
    setLoading(true);
    setError("");
    try {
      const endpoint = phone ? `pets/all/?phone=${encodeURIComponent(phone)}` : "pets/all/";
      const res = await API.get(endpoint);
      setPets(res.data);
    } catch (err) {
      setError("Unable to load pets.");
    } finally {
      setLoading(false);
    }
  };

  const loadCreatedOwners = async () => {
    try {
      const res = await API.get("pets/doctor/created-owners/");
      setCreatedOwners(res.data);
    } catch (err) {
      setCreatedOwners([]);
    }
  };

  useEffect(() => {
    if (userId) {
      API.get("accounts/me/")
        .then((res) => {
          const status = res.data.doctor_status || "pending";
          setDoctorStatus(status);
          setDoctorProfile({
            username: res.data.username || "",
            bio: res.data.bio || "",
            profile_photo_url: res.data.profile_photo_url || "",
            email: res.data.email || "",
            phone: res.data.phone || "",
          });
          setProfileForm({
            username: res.data.username || "",
            bio: res.data.bio || "",
            email: res.data.email || "",
            phone: res.data.phone || "",
          });
          if (status === "approved") {
            loadPets();
            loadCreatedOwners();
          } else {
            setPets([]);
            setCreatedOwners([]);
          }
        })
        .catch(() => {
          setError("Unable to load doctor status.");
        });
    }
  }, [userId]);

  const logout = () => {
    localStorage.clear();
    window.location.href = "/";
  };

  const handleCreateOwnerPet = async () => {
    setCreateError("");
    setCreateMessage("");
    const requiredFields = [
      ["owner_username", "Owner username"],
      ["owner_email", "Owner email"],
      ["owner_phone", "Owner phone"],
      ["pet_name", "Pet name"],
      ["pet_breed", "Pet breed"],
      ["pet_age", "Pet age"],
      ["pet_vaccination_date", "Last vaccination date"],
    ];
    const missingField = requiredFields.find(([field]) => !String(createForm[field] || "").trim());
    if (missingField) {
      setCreateError(`${missingField[1]} is required.`);
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(createForm.owner_email.trim())) {
      setCreateError("Enter a valid owner email address.");
      return;
    }
    const lengthError = phoneLengthError(createForm.owner_phone, ownerCountry);
    if (lengthError) {
      setCreateError(lengthError);
      return;
    }
    const ownerPhone = parseSelectedPhone(createForm.owner_phone, ownerCountry);
    if (!ownerPhone || !ownerPhone.isValid()) {
      setCreateError("Enter a valid owner phone number for the selected country.");
      return;
    }
    setCreating(true);
    try {
      const payload = {
        owner_username: createForm.owner_username,
        owner_email: createForm.owner_email,
        owner_phone: ownerPhone.number,
        owner_password: createForm.owner_password,
        pet_name: createForm.pet_name,
        pet_breed: createForm.pet_breed,
        pet_age: createForm.pet_age,
        pet_vaccination_date: createForm.pet_vaccination_date,
      };
      const res = await API.post("pets/doctor/add-owner-pet/", payload);
      const generated = res.data.generated_password;
      const temporaryPassword = generated || createForm.owner_password;
      const emailNotice = res.data.email_sent
        ? ` Welcome email sent to ${res.data.email_recipient || createForm.owner_email}.`
        : "";
      setCreateMessage(
        temporaryPassword
          ? `Owner and pet created. Temporary owner password: ${temporaryPassword}. Owner must reset on first login.${emailNotice}`
          : `Owner and pet created successfully.${emailNotice}`
      );
      setCreateForm({
        owner_username: "",
        owner_email: "",
        owner_phone: "",
        owner_password: "",
        pet_name: "",
        pet_breed: "",
        pet_age: "",
        pet_vaccination_date: "",
      });
      loadPets(phoneSearch);
      loadCreatedOwners();
    } catch (err) {
      const data = err?.response?.data;
      if (typeof data === "object" && data !== null) {
        const firstError = Object.values(data)[0];
        setCreateError(Array.isArray(firstError) ? firstError[0] : String(firstError));
      } else {
        setCreateError("Unable to create owner and pet.");
      }
    } finally {
      setCreating(false);
    }
  };

  const openNewPetRegistry = () => {
    if (!isOnboardingOpen) {
      setIsOnboardingOpen(true);
      // Allow the slide to expand before focusing for better UX.
      setTimeout(() => {
        onboardingFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        ownerUsernameInputRef.current?.focus();
      }, 260);
      return;
    }
    onboardingFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    ownerUsernameInputRef.current?.focus();
  };

  const updateDoctorProfile = async () => {
    setProfileError("");
    setProfileMessage("");
    const formData = new FormData();
    formData.append("username", profileForm.username);
    formData.append("bio", profileForm.bio);
    formData.append("email", profileForm.email);
    formData.append("phone", profileForm.phone);
    if (profilePhoto) {
      formData.append("profile_photo", profilePhoto);
    }
    setProfileSaving(true);
    try {
      const res = await API.patch("accounts/profile/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDoctorProfile({
        username: res.data.username || "",
        bio: res.data.bio || "",
        profile_photo_url: res.data.profile_photo_url || doctorProfile.profile_photo_url,
        email: res.data.email || "",
        phone: res.data.phone || "",
      });
      setProfileForm({
        username: res.data.username || "",
        bio: res.data.bio || "",
        email: res.data.email || "",
        phone: res.data.phone || "",
      });
      setProfilePhoto(null);
      setProfileMessage("Profile updated successfully.");
    } catch (err) {
      const data = err?.response?.data;
      if (data && typeof data === "object") {
        const firstKey = Object.keys(data)[0];
        const firstVal = data[firstKey];
        setProfileError(Array.isArray(firstVal) ? firstVal[0] : String(firstVal));
      } else {
        setProfileError("Failed to update profile.");
      }
    } finally {
      setProfileSaving(false);
    }
  };

  return (
    <div className="dashboard-wrap">
      <div className="container">
        {/* Top Header */}
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h2 className="fw-800 text-dark mb-0">Doctor Dashboard</h2>
          <button className="btn btn-outline-danger rounded-pill px-4 fw-bold" onClick={logout}>
            Logout
          </button>
        </div>

        {/* Doctor Identity Card */}
        <div className="doctor-main-card mb-4">
          <div className="d-flex flex-wrap justify-content-between align-items-center gap-4">
            <div className="d-flex align-items-center gap-3">
              <img
                src={doctorProfile.profile_photo_url || "https://via.placeholder.com/80?text=Dr"}
                alt={doctorProfile.username || "Doctor"}
                className="doctor-profile-avatar"
              />
              <div className="doctor-info-section">
                <h5>Dr. {doctorProfile.username || "Doctor"}</h5>
                {doctorProfile.bio && <p className="mb-2 text-muted small">{doctorProfile.bio}</p>}
                <div className="text-muted small">
                  {doctorProfile.email && <span className="me-3">{doctorProfile.email}</span>}
                  {doctorProfile.phone && <span>{doctorProfile.phone}</span>}
                </div>
                <div className="d-flex align-items-center gap-2">
                  <span className="status-label-text">Status:</span>
                  <span className={`badge ${statusBadgeClass} px-3 py-2 rounded-pill`}>{statusLabel}</span>
                </div>
              </div>
            </div>
            
            <div className="text-md-end">
              <p className="text-muted small mb-0 max-width-300">
                Only approved doctors can access medical records and submit summaries.
              </p>
            </div>
          </div>
        </div>

        {/* Profile Settings */}
        <div className="doctor-main-card mb-4">
          <div className="d-flex justify-content-between align-items-center flex-wrap gap-3 mb-3">
            <div>
              <h6 className="fw-bold mb-1">Profile Settings</h6>
              <p className="text-muted small mb-0">Update your name, contact info and display photo.</p>
            </div>
            <div className="d-flex gap-2">
              {showProfileEdit && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={updateDoctorProfile}
                  disabled={profileSaving}
                >
                  {profileSaving ? "Saving..." : "Save Changes"}
                </button>
              )}
              <button
                className="btn btn-outline-primary btn-sm"
                onClick={() => setShowProfileEdit((v) => !v)}
              >
                {showProfileEdit ? "Close" : "Edit Profile"}
              </button>
            </div>
          </div>
          {showProfileEdit && (
            <>
              <div className="doctor-create-grid">
                <div>
                  <label className="form-label small fw-semibold mb-1">Display Name</label>
                  <input
                    className="form-control form-control-sm"
                    value={profileForm.username}
                    onChange={(e) => setProfileForm({ ...profileForm, username: e.target.value })}
                    placeholder="Dr. Jane Doe"
                  />
                </div>
                <div>
                  <label className="form-label small fw-semibold mb-1">Email</label>
                  <input
                    className="form-control form-control-sm"
                    type="email"
                    value={profileForm.email}
                    onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                    placeholder="doctor@email.com"
                  />
                </div>
                <div>
                  <label className="form-label small fw-semibold mb-1">Phone</label>
                  <input
                    className="form-control form-control-sm"
                    value={profileForm.phone}
                    onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                    placeholder="+1 555 123 4567"
                  />
                </div>
                <div>
                  <label className="form-label small fw-semibold mb-1">Bio</label>
                  <input
                    className="form-control form-control-sm"
                    value={profileForm.bio}
                    onChange={(e) => setProfileForm({ ...profileForm, bio: e.target.value })}
                    placeholder="Short professional bio"
                  />
                </div>
                <div>
                  <label className="form-label small fw-semibold mb-1">Profile Photo</label>
                  <input
                    className="form-control form-control-sm"
                    type="file"
                    accept="image/*"
                    onChange={(e) => setProfilePhoto(e.target.files?.[0] || null)}
                  />
                </div>
              </div>
              {profileError && <div className="alert alert-danger mt-3 mb-0 py-2">{profileError}</div>}
              {profileMessage && <div className="alert alert-success mt-3 mb-0 py-2">{profileMessage}</div>}
            </>
          )}
        </div>

        {/* Search & Table Section */}
        <div className="table-card">
          <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
            <h5 className="fw-bold mb-0">Pet Registry</h5>
            
            <div className="d-flex gap-2">
              <button
                className="btn btn-success btn-sm"
                disabled={doctorStatus !== "approved"}
                onClick={openNewPetRegistry}
                aria-expanded={isOnboardingOpen}
              >
                New Pet Registry
              </button>
              <input
                className="form-control form-control-sm"
                placeholder="Owner phone..."
                style={{width: '200px'}}
                value={phoneSearch}
                disabled={doctorStatus !== "approved"}
                onChange={(e) => setPhoneSearch(e.target.value)}
              />
              <button className="btn btn-primary btn-sm" disabled={doctorStatus !== "approved"} onClick={() => loadPets(phoneSearch)}>
                Search
              </button>
              <button
                className="btn btn-outline-secondary btn-sm"
                disabled={doctorStatus !== "approved"}
                onClick={() => {
                  setPhoneSearch("");
                  loadPets("");
                }}
              >
                Reset
              </button>
            </div>
          </div>

          {doctorStatus !== "approved" ? (
            <div className="text-center py-5 bg-light rounded-4">
              <p className="text-warning fw-bold mb-1">Account Pending Approval</p>
              <p className="text-muted small mb-0">Please wait for the administrator to verify your credentials.</p>
            </div>
          ) : (
            <>
              <div
                className={`onboarding-slide ${isOnboardingOpen ? "open" : ""}`}
                ref={onboardingFormRef}
              >
                <div className="doctor-create-card mb-4">
                  <h6 className="fw-bold mb-1">Owner Onboarding</h6>
                  <p className="text-muted small mb-3">Create a new pet owner account and register their first pet.</p>
                  <div className="doctor-create-grid">
                    <div>
                      <label className="form-label small fw-semibold mb-1">Owner Username</label>
                      <input
                        ref={ownerUsernameInputRef}
                        className="form-control form-control-sm"
                        placeholder="Owner Username"
                        value={createForm.owner_username}
                        onChange={(e) => setCreateForm({ ...createForm, owner_username: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="form-label small fw-semibold mb-1">Owner Email</label>
                      <input
                        className="form-control form-control-sm"
                        placeholder="Owner Email"
                        type="email"
                        value={createForm.owner_email}
                        onChange={(e) => setCreateForm({ ...createForm, owner_email: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="form-label small fw-semibold mb-1">Owner Phone</label>
                      <div className="phone-input-group">
                        <select
                          className="form-control form-control-sm phone-country"
                          value={ownerCountry}
                          onChange={(e) => setOwnerCountry(e.target.value)}
                          aria-label="Owner phone country"
                        >
                          {countries.map((item) => (
                            <option key={item.code} value={item.code}>
                              {item.flag} {item.name} (+{item.callingCode})
                            </option>
                          ))}
                        </select>
                        <input
                          className="form-control form-control-sm phone-number"
                          placeholder="Owner Phone"
                          type="tel"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          value={createForm.owner_phone}
                          onChange={(e) =>
                            setCreateForm({
                              ...createForm,
                              owner_phone: e.target.value.replace(/\D/g, ""),
                            })
                          }
                        />
                      </div>
                    </div>
                    <div>
                      <label className="form-label small fw-semibold mb-1">Temporary Password (Optional)</label>
                      <input
                        className="form-control form-control-sm"
                        placeholder="Owner Password (optional)"
                        type="password"
                        value={createForm.owner_password}
                        onChange={(e) => setCreateForm({ ...createForm, owner_password: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="form-label small fw-semibold mb-1">Pet Name</label>
                      <input
                        className="form-control form-control-sm"
                        placeholder="Pet Name"
                        value={createForm.pet_name}
                        onChange={(e) => setCreateForm({ ...createForm, pet_name: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="form-label small fw-semibold mb-1">Pet Breed</label>
                      <input
                        className="form-control form-control-sm"
                        placeholder="Pet Breed"
                        value={createForm.pet_breed}
                        onChange={(e) => setCreateForm({ ...createForm, pet_breed: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="form-label small fw-semibold mb-1">Pet Age (Years)</label>
                      <input
                        className="form-control form-control-sm"
                        placeholder="Pet Age"
                        type="number"
                        min="0"
                        step="0.01"
                        value={createForm.pet_age}
                        onChange={(e) => setCreateForm({ ...createForm, pet_age: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="form-label small fw-semibold mb-1">Last Vaccination Date</label>
                      <input
                        className="form-control form-control-sm"
                        type="date"
                        value={createForm.pet_vaccination_date}
                        onChange={(e) => setCreateForm({ ...createForm, pet_vaccination_date: e.target.value })}
                      />
                    </div>
                  </div>
                  <div className="d-flex justify-content-end mt-3">
                    <button className="btn btn-primary btn-sm" onClick={handleCreateOwnerPet} disabled={creating}>
                      {creating ? "Creating..." : "Create Owner + Pet"}
                    </button>
                  </div>
                  {createError && <div className="alert alert-danger mt-3 mb-0 py-2">{createError}</div>}
                  {createMessage && <div className="alert alert-success mt-3 mb-0 py-2">{createMessage}</div>}
                </div>
              </div>

              {error && <div className="alert alert-danger rounded-3">{error}</div>}
              <div className="table-responsive mb-4">
                <h6 className="fw-bold mb-1">Doctor-Created Owner Accounts</h6>
                <p className="text-muted small mb-3">Track accounts you onboarded and their password-reset status.</p>
                <table className="table table-hover align-middle">
                  <thead>
                    <tr>
                      <th>Owner</th>
                      <th>Email</th>
                      <th>Phone</th>
                      <th>Reset Required</th>
                      <th>Pets</th>
                    </tr>
                  </thead>
                  <tbody>
                    {createdOwners.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center py-3 text-muted">
                          No owners created by you yet.
                        </td>
                      </tr>
                    ) : (
                      createdOwners.map((owner) => (
                        <tr key={owner.id}>
                          <td>{owner.username}</td>
                          <td>{owner.email}</td>
                          <td>{owner.phone}</td>
                          <td>{owner.force_password_reset ? "Yes" : "No"}</td>
                          <td>{owner.pets?.map((p) => p.name).join(", ") || "-"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              {loading ? (
                <div className="text-center py-4"><p className="text-muted">Loading pets...</p></div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-hover align-middle">
                    <thead>
                      <tr>
                        <th>Pet Name</th>
                        <th>Breed</th>
                        <th>Age</th>
                        <th>Owner</th>
                        <th>Phone</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pets.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="text-center py-4 text-muted">No pets found matching your criteria.</td>
                        </tr>
                      ) : (
                        pets.map((pet) => (
                          <tr key={pet.id}>
                            <td className="fw-bold">{pet.name}</td>
                            <td><span className="badge bg-light text-dark">{pet.breed}</span></td>
                            <td>{pet.age} Years</td>
                            <td>{pet.owner_username || pet.owner}</td>
                            <td>{pet.owner_phone || "-"}</td>
                            <td>
                              <Link className="btn btn-outline-primary btn-sm px-3 rounded-pill" to={`/pets/${pet.id}`}>
                                View Details
                              </Link>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default DoctorDashboard;
