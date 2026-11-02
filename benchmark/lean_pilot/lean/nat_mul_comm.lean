namespace MathesisPilot
theorem lean_nat_mul_comm : ∀ (a b : Nat), a * b = b * a := by
  intro a
  intro b
  exact Nat.mul_comm a b
end MathesisPilot
