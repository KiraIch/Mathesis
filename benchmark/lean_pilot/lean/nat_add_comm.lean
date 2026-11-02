namespace MathesisPilot
theorem lean_nat_add_comm : ∀ (a b : Nat), a + b = b + a := by
  intro a
  intro b
  exact Nat.add_comm a b
end MathesisPilot
