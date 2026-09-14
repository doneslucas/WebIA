import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";

import { generateQuiz } from "../services/api";


export type QuizQuestion = {
  question: string;
  options: string[];
  correct_answer: number;
  explanation: string;
};


type QuizContextType = {
  document: string;
  questionCount: string;
  difficulty: string;

  questions: QuizQuestion[];

  quizStarted: boolean;
  currentQuestion: number;

  answers: number[];

  showCorrection: boolean;
  finished: boolean;

  loading: boolean;
  message: string;

  setDocument: (value: string) => void;
  setQuestionCount: (value: string) => void;
  setDifficulty: (value: string) => void;

  startQuiz: () => Promise<void>;

  selectAnswer: (answerIndex: number) => void;
  showQuestionCorrection: () => void;
  nextQuestion: () => void;
  previousQuestion: () => void;

  returnToQuizHome: () => void;

  score: number;
};


const QuizContext =
  createContext<QuizContextType | undefined>(
    undefined
  );


type QuizProviderProps = {
  children: ReactNode;
};


export function QuizProvider({
  children,
}: QuizProviderProps) {

  const [document, setDocument] =
    useState("all");

  const [questionCount, setQuestionCount] =
    useState("10");

  const [difficulty, setDifficulty] =
    useState("medium");


  const [questions, setQuestions] =
    useState<QuizQuestion[]>([]);


  const [quizStarted, setQuizStarted] =
    useState(false);

  const [currentQuestion, setCurrentQuestion] =
    useState(0);


  const [answers, setAnswers] =
    useState<number[]>([]);


  const [showCorrection, setShowCorrection] =
    useState(false);

  const [finished, setFinished] =
    useState(false);


  const [loading, setLoading] =
    useState(false);

  const [message, setMessage] =
    useState("");


  async function startQuiz() {

    setMessage("");
    setLoading(true);

    try {

      const result = await generateQuiz(
        document,
        Number(questionCount),
        difficulty
      );


      if (!result.response.ok) {
        throw new Error(
          result.data.detail ||
          "Erreur lors de la génération du quiz."
        );
      }


      if (
        !result.data.questions ||
        !Array.isArray(result.data.questions)
      ) {
        throw new Error(
          "Le serveur n'a pas retourné de questions valides."
        );
      }


      setQuestions(
        result.data.questions
      );

      setCurrentQuestion(0);

      setAnswers([]);

      setShowCorrection(false);

      setFinished(false);

      setQuizStarted(true);


    } catch (error) {

      console.error(error);


      if (error instanceof Error) {

        setMessage(error.message);

      } else {

        setMessage(
          "Une erreur est survenue lors de la génération du quiz."
        );

      }

    } finally {

      setLoading(false);

    }
  }


  function selectAnswer(
    answerIndex: number
  ) {

    if (showCorrection || finished) {
      return;
    }


    setAnswers((previous) => {

      const updated = [...previous];

      updated[currentQuestion] =
        answerIndex;

      return updated;

    });


    setMessage("");
  }


  function showQuestionCorrection() {

    if (
      answers[currentQuestion] ===
      undefined
    ) {

      setMessage(
        "Veuillez sélectionner une réponse avant de continuer."
      );

      return;
    }


    setMessage("");

    setShowCorrection(true);
  }


  function nextQuestion() {

    if (
      currentQuestion ===
      questions.length - 1
    ) {

      setFinished(true);

      setShowCorrection(false);

      return;
    }


    setCurrentQuestion(
      (previous) => previous + 1
    );

    setShowCorrection(false);

    setMessage("");
  }


  function previousQuestion() {

    if (showCorrection) {
      return;
    }


    if (currentQuestion === 0) {
      return;
    }


    setMessage("");


    setCurrentQuestion(
      (previous) => previous - 1
    );
  }


  function returnToQuizHome() {

    setQuizStarted(false);

    setCurrentQuestion(0);

    setAnswers([]);

    setShowCorrection(false);

    setFinished(false);

    setQuestions([]);

    setMessage("");
  }


  const score = answers.reduce(
    (
      total,
      answer,
      index
    ) => {

      if (
        answer !== undefined &&
        answer ===
          questions[index]?.correct_answer
      ) {

        return total + 1;

      }

      return total;

    },
    0
  );


  return (
    <QuizContext.Provider
      value={{
        document,
        questionCount,
        difficulty,

        questions,

        quizStarted,
        currentQuestion,

        answers,

        showCorrection,
        finished,

        loading,
        message,

        setDocument,
        setQuestionCount,
        setDifficulty,

        startQuiz,

        selectAnswer,
        showQuestionCorrection,
        nextQuestion,
        previousQuestion,

        returnToQuizHome,

        score,
      }}
    >
      {children}
    </QuizContext.Provider>
  );
}


export function useQuiz() {

  const context =
    useContext(QuizContext);


  if (!context) {

    throw new Error(
      "useQuiz doit être utilisé à l'intérieur de QuizProvider."
    );

  }


  return context;
}