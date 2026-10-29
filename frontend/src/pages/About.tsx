
import { useEffect, useState } from "react";

import "./About.css";

type PartnerLogoProps = {
  name: string;
  imagePath: string;
  description: string;
};

function PartnerLogo({
  name,
  imagePath,
  description,
}: PartnerLogoProps) {
  const [imageUnavailable, setImageUnavailable] = useState(false);

  return (
    <div className="about-partner">
      <div className="about-partner-image">
        {!imageUnavailable ? (
          <img
            src={imagePath}
            alt={`Logo ${name}`}
            onError={() => setImageUnavailable(true)}
          />
        ) : (
          <div className="about-logo-placeholder">
            <span className="about-placeholder-icon">＋</span>
            <strong>Logo {name}</strong>
            <span>Image introuvable</span>
          </div>
        )}
      </div>

      <h3>{name}</h3>
      <p>{description}</p>
    </div>
  );
}

function About() {
  useEffect(() => {
    document.title = "À propos de CyberIA";
  }, []);

  return (
    <main className="about-page">
      <section className="about-hero">
        <span className="about-eyebrow">
          CYBERIA · PRÉSENTATION DU PROJET
        </span>

        <h1>À propos de CyberIA</h1>

        <p className="about-intro">
          CyberIA est une plateforme dédiée à l’apprentissage de la
          cybersécurité, associant intelligence artificielle,
          ressources documentaires et exercices interactifs.
        </p>

        <a
          className="about-github-button"
          href="https://github.com/doneslucas/WebIA"
          target="_blank"
          rel="noopener noreferrer"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            className="about-github-icon"
          >
            <path
              fill="currentColor"
              d="M12 .9a11.1 11.1 0 0 0-3.51 21.63c.56.1.76-.24.76-.54v-2.1c-3.1.68-3.76-1.32-3.76-1.32-.51-1.3-1.24-1.65-1.24-1.65-1.02-.7.08-.69.08-.69 1.13.08 1.72 1.16 1.72 1.16 1 1.71 2.63 1.22 3.27.93.1-.73.39-1.22.71-1.5-2.47-.28-5.07-1.24-5.07-5.5 0-1.22.44-2.22 1.16-3-.12-.28-.5-1.42.11-2.96 0 0 .95-.3 3.05 1.15a10.6 10.6 0 0 1 5.55 0c2.1-1.45 3.05-1.15 3.05-1.15.61 1.54.23 2.68.11 2.96.72.78 1.16 1.78 1.16 3 0 4.27-2.6 5.21-5.08 5.49.4.35.76 1.02.76 2.06v3.17c0 .3.2.65.77.54A11.1 11.1 0 0 0 12 .9Z"
            />
          </svg>
          Voir le projet sur GitHub
          <span aria-hidden="true">↗</span>
        </a>
      </section>

      <section className="about-section">
        <div className="about-section-heading">
          <span className="about-section-number">01</span>
          <div>
            <h2>Le projet CyberIA</h2>
            <p>
              Une plateforme web conçue pour découvrir, comprendre
              et réviser les notions essentielles de cybersécurité.
            </p>
          </div>
        </div>

        <div className="about-features">
          <article className="about-feature">
            <span className="about-feature-icon">✦</span>
            <h3>Intelligence artificielle</h3>
            <p>
              Un assistant conversationnel permettant de poser des
              questions et d’obtenir de l’aide dans son apprentissage.
            </p>
          </article>

          <article className="about-feature">
            <span className="about-feature-icon">▤</span>
            <h3>Ressources documentaires</h3>
            <p>
              Des documents PDF exploités pour faciliter l’accès
              aux connaissances et aux informations en cybersécurité.
            </p>
          </article>

          <article className="about-feature">
            <span className="about-feature-icon">✓</span>
            <h3>Quiz et progression</h3>
            <p>
              Des exercices interactifs pour tester ses connaissances
              et suivre son évolution.
            </p>
          </article>
        </div>
      </section>

      <section className="about-section">
        <div className="about-section-heading">
          <span className="about-section-number">02</span>
          <div>
            <h2>Cadre du projet</h2>
            <p>
              Un projet réalisé dans le cadre d’une expérience
              professionnelle et d’un parcours de formation.
            </p>
          </div>
        </div>

        <div className="about-partners">
          <PartnerLogo
            name="Dell Technologies"
            imagePath="/images/dell-technologies-vector-logo.png"
            description="Entreprise d’accueil du stage dans le cadre duquel CyberIA a été développé."
          />

          <PartnerLogo
            name="EPITECH"
            imagePath="/images/epitech-logo-png_seeklogo-628739.png"
            description="Établissement de formation dans le cadre du parcours PGE1."
          />
        </div>
      </section>

      <section className="about-credits">
        <span className="about-section-number">03</span>

        <div className="about-credits-content">
          <span className="about-eyebrow">INFORMATIONS DU PROJET</span>
          <h2>Crédits et réalisation</h2>

          <p>
            <strong>CyberIA</strong> a été conçu et développé
            individuellement dans le cadre d’un stage chez Dell
            Technologies, au cours du parcours EPITECH PGE1.
          </p>

          <p>
            <strong>Conception et développement :</strong> Lucas.
          </p>

          <p>
            <strong>Technologies utilisées :</strong> React,
            TypeScript, FastAPI, PostgreSQL, ChromaDB, Ollama et Docker.
          </p>

          <p className="about-thanks">
            Ce projet représente un travail personnel de conception,
            de développement et d’intégration autour de l’intelligence
            artificielle et de la cybersécurité.
          </p>

          <a
            className="about-source-link"
            href="https://github.com/doneslucas/WebIA"
            target="_blank"
            rel="noopener noreferrer"
          >
            Consulter le code source sur GitHub ↗
          </a>
        </div>
      </section>

      <footer className="about-footer">
        CyberIA · Plateforme d’apprentissage de la cybersécurité
      </footer>
    </main>
  );
}

export default About;
