import Mathlib
namespace MathesisHard
def dbl : List ℕ → List ℕ
  | [] => []
  | x :: xs => (2 * x) :: dbl xs

theorem lean_custom_dbl_length : ∀ l : List ℕ, (dbl l).length = l.length := by
  intro l
  induction l with
  | nil => rfl
  | cons x xs ih => simp [dbl, ih]
end MathesisHard
