import Mathlib
namespace MathesisPilot
theorem lean_nat_dvd_chain4 : ∀ (a b c d : Nat), a ∣ b → b ∣ c → c ∣ d → a ∣ d := by
  intro a
  intro b
  intro c
  intro d
  intro h1
  intro h2
  intro h3
  have h4 : a ∣ c := dvd_trans h1 h2
  have h5 : a ∣ d := dvd_trans h4 h3
  exact h5
end MathesisPilot
