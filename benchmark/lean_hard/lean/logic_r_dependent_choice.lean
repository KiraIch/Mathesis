import Mathlib
namespace MathesisHard
theorem lean_logic_r_dependent_choice : ∀ R : ℕ → ℕ → Prop, (∀ n, ∃ m, R n m) → ∀ a : ℕ, ∃ f : ℕ → ℕ, f 0 = a ∧ ∀ k, R (f k) (f (k + 1)) := by
  intro R h a
  have key : ∃ g : ℕ → ℕ, ∀ n, R n (g n) := ⟨fun n => (h n).choose, fun n => (h n).choose_spec⟩
  obtain ⟨g, hg⟩ := key
  refine ⟨fun k => g^[k] a, rfl, fun k => ?_⟩
  simp only [Function.iterate_succ_apply']
  exact hg _
end MathesisHard
