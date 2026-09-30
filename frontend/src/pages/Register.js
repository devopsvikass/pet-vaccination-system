import React, { useMemo, useState } from "react";
import API from "../api";
import { Link, useNavigate } from "react-router-dom";
import { countries, parseSelectedPhone, phoneLengthError } from "../utils/phone";
import "./Register.css";

function Register({ presetRole = null, title = "Create Account" }) {
  const [form, setForm] = useState({ role: presetRole || "" });
  const [country, setCountry] = useState("IN");
  const [countrySearch, setCountrySearch] = useState("");
  const [countryDropdownOpen, setCountryDropdownOpen] = useState(false);
  const [profilePhoto, setProfilePhoto] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const selectedCountry = countries.find((item) => item.code === country) || countries[0];

  const filteredCountries = useMemo(() => {
    const query = countrySearch.trim().toLowerCase();
    if (!query) {
      return countries;
    }
    return countries.filter((item) => {
      const searchable = `${item.name} ${item.code} ${item.callingCode}`.toLowerCase();
      return searchable.includes(query);
    });
  }, [countrySearch]);

  const handlePhoneChange = (value) => {
    const cleaned = value.replace(/[^\d+]/g, "");
    setForm({ ...form, phone: cleaned });
  };

  const handleRegister = async () => {
    setError("");
    if (/[^\d+\s]/.test(form.phone || "")) {
      setError("Phone number must contain digits only. Letters are not allowed.");
      return;
    }
    const lengthError = phoneLengthError(form.phone, country);
    if (lengthError) {
      setError(lengthError);
      return;
    }
    const phoneNumber = parseSelectedPhone(form.phone, country);
    if (!phoneNumber || !phoneNumber.isValid()) {
      setError("Enter a valid phone number for the selected country.");
      return;
    }
    try {
      const payload = new FormData();
      payload.append("username", form.username || "");
      payload.append("email", form.email || "");
      payload.append("phone", phoneNumber.number);
      payload.append("password", form.password || "");
      payload.append("role", presetRole || form.role || "");
      if ((presetRole || form.role) === "doctor") {
        payload.append("bio", form.bio || "");
        if (profilePhoto) {
          payload.append("profile_photo", profilePhoto);
        }
      }

      await API.post("accounts/register/", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if ((presetRole || form.role) === "doctor") {
        alert("Doctor registered successfully. Please wait for admin approval and verification before login.");
      } else {
        alert("Registered Successfully. Please login.");
      }
      navigate((presetRole || form.role) === "doctor" ? "/doctor-login" : "/owner-login");
    } catch (err) {
      const responseErrors = err?.response?.data;
      const firstError = responseErrors && typeof responseErrors === "object"
        ? Object.values(responseErrors).flat()[0]
        : null;
      setError(firstError || "Registration failed. Check all fields and try again.");
    }
  };

  return (
    <div className="register-shell">
      <div className="register-card">
        <div className="d-flex justify-content-between mb-3">
          <button className="btn btn-outline-secondary btn-sm" onClick={() => navigate(-1)}>
            Back
          </button>
          <Link className="btn btn-outline-primary btn-sm" to="/">
            Home Page
          </Link>
        </div>
        <h2>{title}</h2>

        <div className="form-group">
          <input className="form-control"
            placeholder="Username"
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />

          <input className="form-control"
            placeholder="Email Address"
            type="email"
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />

          <div className="phone-input-group">
            <div className="country-select-wrap">
              <button
                type="button"
                className="form-control country-select-button"
                onClick={() => setCountryDropdownOpen((open) => !open)}
                aria-label="Select country code"
              >
                {selectedCountry.flag} {selectedCountry.name} (+{selectedCountry.callingCode})
              </button>

              {countryDropdownOpen && (
                <div className="country-dropdown">
                  <div className="country-search-row">
                    <input
                      type="search"
                      className="form-control country-search-input"
                      placeholder="Search country"
                      value={countrySearch}
                      onChange={(e) => setCountrySearch(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-sm btn-success country-search-button"
                      onClick={() => setCountryDropdownOpen(false)}
                    >
                      Search
                    </button>
                  </div>

                  <div className="country-list">
                    {filteredCountries.length > 0 ? (
                      filteredCountries.map((item) => (
                        <button
                          type="button"
                          key={item.code}
                          className={`country-option ${country === item.code ? "selected" : ""}`}
                          onClick={() => {
                            setCountry(item.code);
                            setCountrySearch("");
                            setCountryDropdownOpen(false);
                          }}
                        >
                          <span>{item.flag}</span>
                          <span>{item.name}</span>
                          <span>(+{item.callingCode})</span>
                        </button>
                      ))
                    ) : (
                      <div className="country-empty">No country found</div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <input
              className="form-control phone-number"
              placeholder="Phone Number"
              type="tel"
              autoComplete="tel-national"
              inputMode="numeric"
              maxLength={country === "IN" ? 10 : 20}
              value={form.phone || ""}
              onChange={(e) => handlePhoneChange(e.target.value)}
            />
          </div>

          <input className="form-control"
            placeholder="Password"
            type="password"
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />

          {!presetRole && (
            <select className="form-control"
              value={form.role || ""}
              onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="">Select Your Role</option>
              <option value="owner">Pet Owner</option>
              <option value="doctor">Veterinary Doctor</option>
            </select>
          )}
        </div>

        {(presetRole || form.role) === "doctor" && (
          <div className="doctor-extra-fields border-top pt-3 mt-2">
            <p className="small text-start fw-bold mb-2">Doctor Profile Information</p>
            <textarea
              className="form-control"
              placeholder="Tell us about your experience (Bio)"
              rows={3}
              onChange={(e) => setForm({ ...form, bio: e.target.value })}
            />
            <label className="small ms-1 text-muted">Upload Professional Photo</label>
            <input
              className="form-control mt-1"
              type="file"
              accept="image/*"
              onChange={(e) => setProfilePhoto(e.target.files?.[0] || null)}
            />
          </div>
        )}

        <button className="btn btn-success w-100 mt-2" onClick={handleRegister}>
          Complete Registration
        </button>

        {error && <p className="text-danger mt-3">{error}</p>}

        <div className="mt-4 border-top pt-3">
          <p>
            Already have an account?{" "}
            <Link to={(presetRole || form.role) === "doctor" ? "/doctor-login" : "/owner-login"}>
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Register;
