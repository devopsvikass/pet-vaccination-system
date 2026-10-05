import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import API from "../api";
import "./AuthHome.css";

function AuthHome() {
  const [doctors, setDoctors] = useState([]);

  useEffect(() => {
    API.get("accounts/approved-doctors/")
      .then((res) => setDoctors(res.data))
      .catch(() => setDoctors([]));
  }, []);

  return (
    <div className="home-page">
      {/* 1. Header Navigation */}
      <nav className="navbar">
        <div className="container nav-wrap">
          <Link className="navbar-brand" to="/">🐾 PetVaccination</Link>
          <div className="nav-right">
            <Link className="btn btn-primary" to="/login">Login / Register</Link>
            <Link className="btn btn-dark nav-admin-btn" to="/admin-login">Admin Login</Link>
          </div>
        </div>
      </nav>

      {/* 2. Hero Section */}
      <header className="home-hero">
        <div className="container">
          <h1>Smart Care For <br /> Your Best Friend.</h1>
          <p className="cicd-test">🚀 CI/CD Deployment Test — Version 2</p>
          <p>
            The all-in-one platform for pet vaccination tracking, 
            doctor consultations, and health record management.
          </p>
        </div>
      </header>

      <main className="container">
        {/* 3. About Section */}
        <section className="home-section">
          <h3>About the System</h3>
          <p className="lead text-muted mb-4">
            We simplify pet healthcare by providing a secure bridge between pet owners and certified veterinary professionals.
          </p>
          <div className="row g-4">
            <div className="col-md-4">
              <div className="p-3 border rounded-4 h-100">
                <h5 className="fw-bold">Vaccine Tracking</h5>
                <p className="small text-muted mb-0">Never miss a booster shot with automated history and reminders.</p>
              </div>
            </div>
            <div className="col-md-4">
              <div className="p-3 border rounded-4 h-100">
                <h5 className="fw-bold">Verified Doctors</h5>
                <p className="small text-muted mb-0">Access a curated list of approved veterinary experts in your area.</p>
              </div>
            </div>
            <div className="col-md-4">
              <div className="p-3 border rounded-4 h-100">
                <h5 className="fw-bold">Secure Data</h5>
                <p className="small text-muted mb-0">Your pet's health records are encrypted and available 24/7.</p>
              </div>
            </div>
          </div>
        </section>

        {/* 4. Doctors Section */}
        <section className="home-section">
          <h3>Our Approved Doctors</h3>
          <div className="doctor-grid">
            {doctors.length === 0 ? (
              <div className="text-center w-100 py-5">
                <p className="text-muted fs-5">Our medical board is currently reviewing new applications.</p>
              </div>
            ) : (
              doctors.map((doctor) => (
                <div key={doctor.id} className="doctor-card">
                  <img
                    src={doctor.profile_photo_url || `https://api.dicebear.com/7.x/adventurer/svg?seed=${doctor.username}`}
                    alt={doctor.username}
                    className="doctor-avatar"
                  />
                  <h5 className="mb-2">Dr. {doctor.username}</h5>
                  <p className="mb-0 text-muted small">{doctor.bio || "Specialized Veterinary Physician"}</p>
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      {/* 5. Footer Section */}
      <footer className="main-footer">
        <div className="container">
          <div className="footer-grid">
            <div className="footer-section">
              <h4>PetVaccination</h4>
              <p className="small">The gold standard in pet health management and vaccination records.</p>
            </div>
            <div className="footer-section">
              <h4>Resources</h4>
              <ul className="footer-links">
                <li><Link to="/about">About Us</Link></li>
                <li><Link to="/faq">Health Tips</Link></li>
                <li><Link to="/privacy">Privacy Policy</Link></li>
              </ul>
            </div>
            <div className="footer-section">
              <h4>Contact</h4>
              <ul className="footer-links">
                <li>support@petvaccine.com</li>
                <li>+91 81155xxxx</li>
                <li>Health City, Sector 4</li>
              </ul>
            </div>
          </div>
          <div className="footer-bottom">
            <p>&copy; 2026 Pet Vaccination System. Keeping paws healthy.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default AuthHome;
