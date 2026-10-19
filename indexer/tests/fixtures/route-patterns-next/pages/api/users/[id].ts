export default async function user(req, res) {
  res.status(200).json({ id: req.query.id })
}
