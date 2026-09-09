import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getProgress } from "../services/api";

import "./Progression.css";


interface QuizResult {
  id: number;
  score: number;
  total_questions: number;
  created_at: string;
}


function Progression() {
  const navigate = useNavigate();

  const [results, setResults] = useState<QuizResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");


  useEffect(() => {
    async function loadProgress() {
      try {
        const { response, data } = await getProgress();

        if (!response.ok) {
          if (response.status === 401) {
            localStorage.removeItem("access_token");
            navigate("/login");
            return;
          }

          setError(
            data.detail ||
              "Impossible de récupérer la progression."
          );

          return;
        }

        setResults(data.results);

      } catch {
        setError(
          "Impossible de contacter le serveur."
        );

      } finally {
        setLoading(false);
      }
    }

    loadProgress();
  }, [navigate]);


  if (loading) {
    return (
      <div className="progression-page">
        <main className="progression-container">
          <div className="progression-header">
            <h1>Ma progression</h1>
            <p>Suivez votre évolution et vos résultats.</p>
          </div>

          <div className="progression-loading">
            Chargement de votre progression...
          </div>
        </main>
      </div>
    );
  }


  if (error) {
    return (
      <div className="progression-page">
        <main className="progression-container">
          <div className="progression-header">
            <h1>Ma progression</h1>
            <p>Suivez votre évolution et vos résultats.</p>
          </div>

          <div className="progression-error">
            {error}
          </div>
        </main>
      </div>
    );
  }


  if (results.length === 0) {
    return (
      <div className="progression-page">
        <main className="progression-container">

          <div className="progression-header">
            <h1>Ma progression</h1>

            <p>
              Suivez votre évolution et vos résultats.
            </p>
          </div>


          <div className="progression-empty">

            <div className="progression-empty-icon">
              📊
            </div>

            <h2>
              Aucun quiz réalisé
            </h2>

            <p>
              Votre progression apparaîtra ici dès que
              vous aurez réalisé votre premier quiz.
            </p>

            <button
              type="button"
              onClick={() => navigate("/chatbot")}
            >
              Retourner au chatbot
            </button>

          </div>

        </main>
      </div>
    );
  }


  const percentages = results.map(
    (result) =>
      (result.score / result.total_questions) * 100
  );


  const totalQuiz = results.length;


  const averageScore =
    percentages.reduce(
      (total, percentage) =>
        total + percentage,
      0
    ) / percentages.length;


  const bestScore = Math.max(
    ...percentages
  );


  const latestResult = results[0];


  const latestPercentage =
    (latestResult.score /
      latestResult.total_questions) *
    100;


  const chronologicalResults = [
    ...results
  ].reverse();


  const chartWidth = 760;
  const chartHeight = 280;

  const chartPaddingLeft = 50;
  const chartPaddingRight = 25;
  const chartPaddingTop = 25;
  const chartPaddingBottom = 45;

  const graphWidth =
    chartWidth -
    chartPaddingLeft -
    chartPaddingRight;

  const graphHeight =
    chartHeight -
    chartPaddingTop -
    chartPaddingBottom;


  const points = chronologicalResults.map(
    (result, index) => {

      const percentage =
        (result.score /
          result.total_questions) *
        100;

      const x =
        chronologicalResults.length === 1
          ? chartWidth / 2
          : chartPaddingLeft +
            (index /
              (chronologicalResults.length - 1)) *
              graphWidth;

      const y =
        chartPaddingTop +
        graphHeight -
        (percentage / 100) *
          graphHeight;

      return {
        x,
        y,
        percentage
      };
    }
  );


  const linePoints = points
    .map(
      (point) =>
        `${point.x},${point.y}`
    )
    .join(" ");


  function formatDate(date: string) {
    return new Date(
      date
    ).toLocaleDateString(
      "fr-FR",
      {
        day: "2-digit",
        month: "2-digit",
        year: "numeric"
      }
    );
  }


  function getResultClass(
    percentage: number
  ) {
    if (percentage >= 80) {
      return "quiz-result excellent";
    }

    if (percentage >= 50) {
      return "quiz-result good";
    }

    return "quiz-result weak";
  }


  function getResultLabel(
    percentage: number
  ) {
    if (percentage >= 80) {
      return "Excellent";
    }

    if (percentage >= 50) {
      return "Réussi";
    }

    return "À améliorer";
  }


  return (
    <div className="progression-page">

      <main className="progression-container">

        <header className="progression-header">

          <div>
            <h1>
              Ma progression
            </h1>

            <p>
              Suivez votre évolution et vos résultats.
            </p>
          </div>

        </header>


        {/* ========================= */}
        {/* STATISTIQUES               */}
        {/* ========================= */}

        <section className="progression-stats">

          <div className="stat-card">

            <div className="stat-icon">
              📝
            </div>

            <div className="stat-content">

              <span className="stat-label">
                Quiz réalisés
              </span>

              <strong className="stat-value">
                {totalQuiz}
              </strong>

            </div>

          </div>


          <div className="stat-card">

            <div className="stat-icon">
              📊
            </div>

            <div className="stat-content">

              <span className="stat-label">
                Score moyen
              </span>

              <strong className="stat-value">
                {Math.round(averageScore)}%
              </strong>

            </div>

          </div>


          <div className="stat-card">

            <div className="stat-icon">
              🏆
            </div>

            <div className="stat-content">

              <span className="stat-label">
                Meilleur score
              </span>

              <strong className="stat-value">
                {Math.round(bestScore)}%
              </strong>

            </div>

          </div>


          <div className="stat-card">

            <div className="stat-icon">
              🎯
            </div>

            <div className="stat-content">

              <span className="stat-label">
                Dernier quiz
              </span>

              <strong className="stat-value">
                {Math.round(latestPercentage)}%
              </strong>

            </div>

          </div>

        </section>


        {/* ========================= */}
        {/* GRAPHIQUE                  */}
        {/* ========================= */}

        <section className="progression-card">

          <div className="section-header">

            <div>
              <h2>
                Évolution des scores
              </h2>

              <p>
                Visualisez votre progression au fil des quiz.
              </p>
            </div>

          </div>


          <div className="chart-container">

            <svg
              viewBox={`0 0 ${chartWidth} ${chartHeight}`}
              className="progression-chart"
              role="img"
              aria-label="Graphique d'évolution des scores"
            >

              {/* Lignes horizontales */}

              {[0, 25, 50, 75, 100].map(
                (value) => {

                  const y =
                    chartPaddingTop +
                    graphHeight -
                    (value / 100) *
                      graphHeight;

                  return (
                    <g key={value}>

                      <line
                        x1={chartPaddingLeft}
                        y1={y}
                        x2={
                          chartWidth -
                          chartPaddingRight
                        }
                        y2={y}
                        className="chart-grid-line"
                      />

                      <text
                        x={chartPaddingLeft - 10}
                        y={y + 4}
                        className="chart-label"
                        textAnchor="end"
                      >
                        {value}%
                      </text>

                    </g>
                  );
                }
              )}


              {/* Ligne du graphique */}

              {points.length > 1 && (
                <polyline
                  points={linePoints}
                  className="chart-line"
                  fill="none"
                />
              )}


              {/* Points */}

              {points.map(
                (point, index) => (
                  <g key={index}>

                    <circle
                      cx={point.x}
                      cy={point.y}
                      r="5"
                      className="chart-point"
                    />

                    <title>
                      Quiz {index + 1} :{" "}
                      {Math.round(
                        point.percentage
                      )}%
                    </title>

                  </g>
                )
              )}


              {/* Dates */}

              {chronologicalResults.map(
                (result, index) => {

                  const point =
                    points[index];

                  return (
                    <text
                      key={result.id}
                      x={point.x}
                      y={
                        chartHeight -
                        15
                      }
                      className="chart-date"
                      textAnchor="middle"
                    >
                      {formatDate(
                        result.created_at
                      )}
                    </text>
                  );
                }
              )}

            </svg>

          </div>

        </section>


        {/* ========================= */}
        {/* HISTORIQUE                 */}
        {/* ========================= */}

        <section className="progression-card">

          <div className="section-header">

            <div>
              <h2>
                Historique des quiz
              </h2>

              <p>
                Retrouvez l'ensemble de vos résultats.
              </p>
            </div>

          </div>


          <div className="quiz-history">

            <div className="quiz-history-header">

              <span>
                Quiz
              </span>

              <span>
                Score
              </span>

              <span>
                Pourcentage
              </span>

              <span>
                Date
              </span>

              <span>
                Résultat
              </span>

            </div>


            {results.map(
              (result, index) => {

                const percentage =
                  Math.round(
                    (result.score /
                      result.total_questions) *
                      100
                  );

                return (
                  <div
                    className="quiz-history-row"
                    key={result.id}
                  >

                    <div className="quiz-number">
                      <span className="quiz-number-icon">
                        📝
                      </span>

                      <strong>
                        Quiz #{results.length - index}
                      </strong>
                    </div>


                    <div className="quiz-score">
                      {result.score} /{" "}
                      {result.total_questions}
                    </div>


                    <div className="quiz-percentage">
                      {percentage}%
                    </div>


                    <div className="quiz-date">
                      {formatDate(
                        result.created_at
                      )}
                    </div>


                    <div
                      className={getResultClass(
                        percentage
                      )}
                    >
                      {getResultLabel(
                        percentage
                      )}
                    </div>

                  </div>
                );
              }
            )}

          </div>

        </section>

      </main>

    </div>
  );
}


export default Progression;