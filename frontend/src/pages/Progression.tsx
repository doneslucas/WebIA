import { useEffect, useState } from "react";

import { getProgress } from "../services/api";


interface QuizResult {
  id: number;
  score: number;
  total_questions: number;
  created_at: string;
}


function Progression() {
  const [results, setResults] = useState<QuizResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");


  useEffect(() => {
    async function loadProgress() {
      try {
        const { response, data } = await getProgress();

        if (!response.ok) {
          setError(
            data.detail || "Impossible de récupérer la progression."
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
  }, []);


  if (loading) {
    return (
      <div>
        <h1>Ma progression</h1>
        <p>Chargement...</p>
      </div>
    );
  }


  if (error) {
    return (
      <div>
        <h1>Ma progression</h1>
        <p>{error}</p>
      </div>
    );
  }


  return (
    <div>
      <h1>Ma progression</h1>

      {results.length === 0 ? (
        <p>
          Aucun quiz réalisé pour le moment.
        </p>
      ) : (
        <div>
          {results.map((result) => {
            const percentage = Math.round(
              (result.score / result.total_questions) * 100
            );

            return (
              <div key={result.id}>
                <p>
                  Score : {result.score} /{" "}
                  {result.total_questions}
                </p>

                <p>
                  Pourcentage : {percentage}%
                </p>

                <p>
                  Date :{" "}
                  {new Date(
                    result.created_at
                  ).toLocaleString("fr-FR")}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


export default Progression;