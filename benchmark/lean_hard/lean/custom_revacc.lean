import Mathlib
namespace MathesisHard
def revAcc : List ℕ → List ℕ → List ℕ
  | [], acc => acc
  | x :: xs, acc => revAcc xs (x :: acc)

theorem lean_custom_revacc : ∀ (l acc : List ℕ), revAcc l acc = l.reverse ++ acc := by
  intro l
  induction l with
  | nil =>
    intro acc
    simp [revAcc]
  | cons x xs ih =>
    intro acc
    simp [revAcc, ih]
end MathesisHard
